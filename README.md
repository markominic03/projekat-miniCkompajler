# MiniC Compiler

Veb-aplikacija koja integriše **Micko** kompajler i **HipSim** simulator u
jedinstveno veb-okruženje. Korisnik unosi miniC kod, dobija generisani
asemblerski kod i prati njegovo izvršavanje korak po korak na hipotetskoj
registarskoj mašini, bez upotrebe terminala.

Diplomski rad *Integracija edukativnog kompajlera i simulatora u jedinstveno
veb-okruženje*, Fakultet tehničkih nauka u Novom Sadu, predmet Programski
prevodioci.

## Pokretanje

Potreban je samo [Docker](https://www.docker.com/). Na Windows-u i macOS-u
Docker Desktop mora biti pokrenut. Flex, Bison, gcc i Python se instaliraju
unutar kontejnera.

```bash
docker compose up --build
```

Zatim u veb-pregledaču otvori **http://localhost:8000**.

> U ispisu servera piše `http://0.0.0.0:8000`. To je adresa na kojoj server
> sluša unutar kontejnera, a ne adresa koja se otvara u veb-pregledaču.

Aplikacija se gasi sa `Ctrl+C`. Opcija `--build` je potrebna samo pri prvom
pokretanju i posle izmena u `code-gen/` ili `backend/`.

**Bez Dockera (Linux ili WSL):** potrebni su `flex`, `bison`, `gcc`, `make` i
Python 3.10+.

```bash
cd code-gen && make && cd ..
pip install -r requirements.txt
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Korišćenje

1. U levo polje unesi miniC kod i klikni **Kompajliraj**.
2. U desnom polju se prikazuje generisani asemblerski kod. Ako kod sadrži
   greške, umesto njega se prikazuju poruke o greškama sa brojem linije.
3. Klikni **Simuliraj**, pa **Sledeća instrukcija** za svaki korak simulacije.
   Prate se registri, statusni flegovi i stek, a na kraju se ispisuje
   povratna vrednost `main` funkcije.

Primer programa, čija je povratna vrednost 15:

```c
int uvecaj(int n) {
    int rez;
    rez = 0;
    if (n > 0)
        rez = n + 10;
    else
        rez = 0 - n;
    return rez;
}
int main() {
    int a;
    int b;
    a = 5;
    b = uvecaj(a);
    return b;
}
```

Jezik miniC podržava tipove `int` i `unsigned`, funkcije sa najviše jednim
parametrom, lokalne promenljive, dodelu, `if`/`else`, `return`, sabiranje,
oduzimanje i relacione operatore.

## Struktura projekta

| Putanja | Namena |
|---|---|
| `code-gen/micko.l` | Flex lekser |
| `code-gen/micko.y` | Bison gramatika, semantičke akcije, generisanje koda |
| `code-gen/codegen.c/.h` | Pomoćne funkcije za generisanje asemblerskih instrukcija |
| `code-gen/symtab.c/.h` | Tabela simbola |
| `code-gen/hipsim-src/` | Originalni HipSim simulator u C-u, samo referenca za Python verziju |
| `backend/main.py` | FastAPI server, 3 HTTP krajnje tačke |
| `backend/simulator.py` | Python reimplementacija HipSim-a |
| `backend/static/index.html` | Klijent (editor, prikaz asemblerskog koda, simulator) |
| `Dockerfile`, `docker-compose.yml` | Pokretanje u Docker kontejneru |

## HTTP krajnje tačke

| Krajnja tačka | Namena |
|---|---|
| `POST /compile` | Prevodi miniC kod (`{"code": "..."}`). Vraća `{"success": true, "asm": "..."}` ili `{"success": false, "error": "..."}` |
| `POST /simulate/init` | Inicijalizuje simulaciju nad poslednjim `output.asm`. Vraća `session_id` i početno stanje |
| `POST /simulate/step/{session_id}` | Izvršava jednu instrukciju i vraća novo stanje |

## Hipotetska registarska mašina

Mašina ima 1024 bajta memorije. Stek raste ka nižim adresama, a početna
vrednost pokazivača na vrh steka je 1024. Mašina ima 16 registara od 32 bita:

| Registar | Namena |
|---|---|
| `%0` – `%12` | Registri opšte namene (međurezultati) |
| `%13` | Povratna vrednost funkcije |
| `%14` | Pokazivač na stek frejm |
| `%15` | Pokazivač na vrh steka |

## Licenca

Datoteke u `code-gen/hipsim-src/` potiču iz HipSim projekta (Žarko Živanov)
i licencirane su pod GPL3 licencom (`code-gen/hipsim-src/gpl.txt`).
