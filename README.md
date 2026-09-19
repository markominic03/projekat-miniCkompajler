# MiniC Compiler

Web aplikacija za kompajliranje **miniC** jezika (podskup C-a) u asemblerski
kod hipotetičkog procesora, sa ugrađenim step-by-step simulatorom za
izvršavanje generisanog koda direktno u browseru.

Projekat je nastao u sklopu kursa Kompajleri i sastoji se iz tri celine:

- **`code-gen/`** — sâm kompajler, napisan u C-u uz pomoć Flex/Bison alata
  (leksička i sintaksna analiza, generisanje asemblerskog koda)
- **`backend/`** — FastAPI server koji poziva kompajler i sadrži Python
  reimplementaciju simulatora (`simulator.py`) za izvršavanje generisanog
  asemblera korak po korak
- **`backend/static/`** — frontend (čist HTML/JS), editor koda i prikaz
  registara/memorije/steka simulatora

## Pokretanje

### Opcija A — Docker (preporučeno, radi na svakom OS-u)

Jedini preduslov je instaliran [Docker](https://www.docker.com/) (sa Docker
Compose pluginom). Nije potrebno ručno instalirati flex, bison, gcc ni Python
— sve se builduje unutar kontejnera.

```bash
docker compose up --build
```

Aplikacija je dostupna na [http://localhost:8000](http://localhost:8000).

Za gašenje:

```bash
docker compose down
```

Nakon prve izgradnje slike, dovoljno je `docker compose up` (bez `--build`),
osim ako su menjani `code-gen/` ili `backend/` fajlovi.

### Opcija B — ručno pokretanje (Linux)

Potrebni alati: `flex`, `bison`, `gcc`, `make`, Python 3.9+.

```bash
# 1. Kompajliraj miniC kompajler
cd code-gen
make

# 2. Instaliraj Python zavisnosti
cd ..
pip install -r requirements.txt

# 3. Pokreni server
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Aplikacija je dostupna na [http://localhost:8000](http://localhost:8000).

## Kako se koristi

1. U editoru na levoj strani napiši miniC kod (primer ispod).
2. Klikni na **Kompajliraj** — dobijaš generisani asemblerski kod hipotetičkog
   procesora.
3. Klikni na **Pokreni simulaciju** i korak po korak prati izvršavanje:
   trenutnu instrukciju, registre, indikatore (Z/S/C/O), globalne promenljive
   i sadržaj steka.

Primer miniC koda (`code-gen/test.mc`):

```c
int duplo(int x) {
   return x + x;
}

int uvecaj(int y) {
   return duplo(y) + 1;
}

int main() {
   return uvecaj(5);
}
```

## Podržan jezik (miniC)

Podskup C-a sa sledećim konstrukcijama:

- tipovi: `int`, `unsigned`
- funkcije sa parametrima i povratnom vrednošću
- `if` / `else`
- `return`
- aritmetički i relacioni izrazi, pozivi funkcija

Gramatika je definisana u `code-gen/micko.y` (Bison), lekser u
`code-gen/micko.l` (Flex), generisanje koda u `code-gen/codegen.c`.

## Instrukcijski skup (asembler hipotetičkog procesora)

Generisani asembler cilja hipotetički procesor sa 16 registara (`%0`–`%15`,
gde je `%14` frame pointer, `%15` stack pointer, `%13` registar za povratnu
vrednost) i podržava instrukcije poput `MOV`, `PUSH`/`POP`, `CALL`/`RET`,
aritmetiku (`ADDS/ADDU`, `SUBS/SUBU`, `MULS/MULU`, `DIVS/DIVU`), poređenje
(`CMPS/CMPU`) i skokove (`JMP`, `JEQ`, `JNE`, `JGTS/JGTU`, ...). Detaljan opis
originalnog **HipSim** simulatora (na kom se zasniva backend implementacija)
nalazi se u `code-gen/hipsim-src/Readme.txt`.

> Napomena: `backend/simulator.py` je Python reimplementacija iste logike
> kao `code-gen/hipsim-src/simulator.c`, tako da izvorni `hipsim` binarni fajl
> nije neophodan za rad web aplikacije — simulacija se izvršava direktno u
> Python procesu radi lakše integracije sa frontendom (step-by-step API).

## API

| Metoda | Ruta                      | Opis                                                        |
|--------|---------------------------|--------------------------------------------------------------|
| GET    | `/`                       | Vraća frontend (`static/index.html`)                         |
| POST   | `/compile`                | Telo: `{"code": "<miniC kod>"}`. Vraća `{"success", "asm"}` ili `{"success": false, "error"}` |
| POST   | `/simulate/init`          | Inicijalizuje simulator nad poslednje generisanim `output.asm` |
| POST   | `/simulate/step/{session_id}` | Izvršava jednu instrukciju u datoj sesiji simulatora     |

## Testiranje kompajlera

U `code-gen/` direktorijumu:

```bash
make test           # kratak ispis (PASSED/FAILED) za sve test*.mc fajlove
make det            # detaljan ispis, uključujući generisani asembler
make det TEST=test.mc   # pokretanje samo određenog test fajla
make clean          # brisanje generisanih fajlova
```

## Struktura projekta

```
.
├── Dockerfile              # multi-stage build (builder: flex/bison/gcc, runtime: Python)
├── docker-compose.yml
├── requirements.txt        # Python zavisnosti backenda
├── code-gen/               # miniC kompajler (C, Flex, Bison)
│   ├── micko.l / micko.y   # leksička i sintaksna analiza
│   ├── codegen.c / .h      # generisanje asemblerskog koda
│   ├── symtab.c / .h       # tabela simbola
│   ├── test.mc             # primer miniC programa
│   └── hipsim-src/         # originalni C simulator hipotetičkog procesora (referenca)
└── backend/
    ├── main.py             # FastAPI server, poziva kompajler kao subprocess
    ├── simulator.py        # Python reimplementacija simulatora
    └── static/index.html   # frontend (editor + prikaz simulacije)
```

## Licenca

Fajlovi u `code-gen/hipsim-src/` potiču iz HipSim projekta (Žarko Živanov) i
licencirani su pod GPL3 licencom (`code-gen/hipsim-src/gpl.txt`).
