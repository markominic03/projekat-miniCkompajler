import os
import subprocess
import threading
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from simulator import Simulator, parse_asm

app = FastAPI()

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
COMPILER_DIR   = os.path.normpath(os.path.join(BASE_DIR, "..", "code-gen"))
TEST_MC        = os.path.join(COMPILER_DIR, "test.mc")
OUTPUT_ASM     = os.path.join(COMPILER_DIR, "output.asm")
MICKO_BIN      = os.path.join(COMPILER_DIR, "micko")
FRONTEND_HTML  = os.path.join(BASE_DIR, "static", "index.html")

compile_lock = threading.Lock()
sim_sessions: dict = {}


class CompileRequest(BaseModel):
    code: str


@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_HTML)


@app.post("/compile")
def compile_code(req: CompileRequest):
    if not os.path.isfile(MICKO_BIN):
        return {
            "success": False,
            "error": "Micko nije pronadjen.\nPokreni 'make' pre pokretanja servera."
        }

    with compile_lock:
        with open(TEST_MC, "w") as f:
            f.write(req.code)

        if os.path.exists(OUTPUT_ASM):
            os.remove(OUTPUT_ASM)

        with open(TEST_MC, "r") as stdin_f:
            result = subprocess.run(
                ["./micko"],
                stdin=stdin_f,
                capture_output=True,
                text=True,
                cwd=COMPILER_DIR
            )

        exit_code  = result.returncode
        stderr_out = result.stderr.strip()
        stdout_out = result.stdout.strip()
        messages   = "\n".join(filter(None, [stderr_out, stdout_out]))

        has_lexical_errors = bool(stdout_out)
        success = not has_lexical_errors and ((exit_code == 0) or (128 <= exit_code <= 254))

        if success and os.path.exists(OUTPUT_ASM):
            with open(OUTPUT_ASM, "r") as f:
                asm_code = f.read()
            return {"success": True, "asm": asm_code}

        error_text = messages if messages else "Nepoznata greska"
        return {"success": False, "error": error_text}


@app.post("/simulate/init")
def simulate_init():
    """Inicijalizuje simulator nad trenutnim output.asm."""
    if not os.path.exists(OUTPUT_ASM):
        raise HTTPException(status_code=400,
                            detail="output.asm ne postoji. Kompajlirajte prvo.")

    with open(OUTPUT_ASM, "r") as f:
        asm_text = f.read()

    sim, error = parse_asm(asm_text)
    if error:
        raise HTTPException(status_code=400,
                            detail=f"Greska pri parsiranju ASM: {error}")

    session_id = str(uuid.uuid4())
    sim_sessions[session_id] = sim

    # Ciscenje starih sesija (max 20)
    if len(sim_sessions) > 20:
        oldest = list(sim_sessions.keys())[0]
        del sim_sessions[oldest]

    return {"session_id": session_id, "state": sim.get_state()}


@app.post("/simulate/step/{session_id}")
def simulate_step(session_id: str):
    """Izvrsava jednu instrukciju u datoj sesiji."""
    sim = sim_sessions.get(session_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Sesija nije pronadjena.")

    if sim.halt:
        return {"state": sim.get_state()}

    try:
        sim.run_once()
    except Exception as e:
        sim.halt = True
        state = sim.get_state()
        state["sim_error"] = str(e)
        return {"state": state}

    return {"state": sim.get_state()}
