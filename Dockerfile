# --- Stage 1: build kompajlera (micko) uz flex/bison/gcc/make ---
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    flex \
    bison \
    gcc \
    libc6-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/code-gen
COPY code-gen/ .
RUN make

# --- Stage 2: runtime (samo Python + skompajlirani binarni fajl) ---
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/code-gen /app/code-gen
COPY backend/ /app/backend/
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

WORKDIR /app/backend

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
