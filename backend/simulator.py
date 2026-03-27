"""
HipSim Python re-implementacija - identična logika kao simulator.c
Podržava isti instruction set i isti memorijski model.
"""

import struct
import re

# Konstante (iz defs.h i simulator.h)
MEM_SIZE         = 1024
REG_NUMBER       = 16
FRAME_POINTER    = 14
STACK_POINTER    = 15
FUNCTION_REGISTER = 13

# Instruction codes
INS_HALT = 1; INS_CALL = 2;  INS_RET  = 3;  INS_PUSH = 4
INS_POP  = 5; INS_CMP  = 6;  INS_JMP  = 7;  INS_JEQ  = 8
INS_JNE  = 9; INS_JGT  = 10; INS_JLT  = 11; INS_JGE  = 12
INS_JLE  = 13; INS_JC  = 14; INS_JNC  = 15; INS_JO   = 16
INS_JNO  = 17; INS_ADD = 18; INS_SUB  = 19; INS_MUL  = 20
INS_DIV  = 21; INS_MOV = 22

# Tip naredbe
NO_TYPE = 0; SIGNED_TYPE = 1; UNSIGNED_TYPE = 2

# Vrste operanada
OP_REGISTER = 1; OP_INDIRECT = 2; OP_INDEX = 3
OP_CONSTANT = 4; OP_ADDRESS  = 5; OP_DATA  = 6

# Tabela naredbi: mnemonic → (inst_code, type)
INST_MAP = {
    'HALT': (INS_HALT, NO_TYPE),     'CALL': (INS_CALL, NO_TYPE),
    'RET':  (INS_RET,  NO_TYPE),     'PUSH': (INS_PUSH, NO_TYPE),
    'POP':  (INS_POP,  NO_TYPE),     'MOV':  (INS_MOV,  NO_TYPE),
    'JMP':  (INS_JMP,  NO_TYPE),     'JEQ':  (INS_JEQ,  NO_TYPE),
    'JNE':  (INS_JNE,  NO_TYPE),     'JC':   (INS_JC,   NO_TYPE),
    'JNC':  (INS_JNC,  NO_TYPE),     'JO':   (INS_JO,   NO_TYPE),
    'JNO':  (INS_JNO,  NO_TYPE),
    'ADDS': (INS_ADD,  SIGNED_TYPE), 'ADDU': (INS_ADD,  UNSIGNED_TYPE),
    'SUBS': (INS_SUB,  SIGNED_TYPE), 'SUBU': (INS_SUB,  UNSIGNED_TYPE),
    'MULS': (INS_MUL,  SIGNED_TYPE), 'MULU': (INS_MUL,  UNSIGNED_TYPE),
    'DIVS': (INS_DIV,  SIGNED_TYPE), 'DIVU': (INS_DIV,  UNSIGNED_TYPE),
    'CMPS': (INS_CMP,  SIGNED_TYPE), 'CMPU': (INS_CMP,  UNSIGNED_TYPE),
    'JGTS': (INS_JGT,  SIGNED_TYPE), 'JGTU': (INS_JGT,  UNSIGNED_TYPE),
    'JLTS': (INS_JLT,  SIGNED_TYPE), 'JLTU': (INS_JLT,  UNSIGNED_TYPE),
    'JGES': (INS_JGE,  SIGNED_TYPE), 'JGEU': (INS_JGE,  UNSIGNED_TYPE),
    'JLES': (INS_JLE,  SIGNED_TYPE), 'JLEU': (INS_JLE,  UNSIGNED_TYPE),
}


class SimError(Exception):
    pass


# Pomocne funkcije za tipove

def _to_word(v):
    """Truncate Python int → int32_t (signed 32-bit)"""
    v = v & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v

def _to_uint64(v):
    """Ensure non-negative uint64 representation"""
    return v & 0xFFFFFFFFFFFFFFFF


# Klasa simulatora

class Simulator:
    def __init__(self):
        # Memorija (1024 bajtova, inicijalizovana na 0xa5 kao u hipsim)
        self.datamem = bytearray([0xa5] * MEM_SIZE)
        # Registri procesora
        self.reg = [0] * REG_NUMBER
        self.reg[STACK_POINTER] = MEM_SIZE  # SP = 1024
        # Program counter i indikatori
        self.pc   = 0
        self.zero = 0; self.sign = 0; self.carry = 0; self.overflow = 0
        self.halt = False
        # Memorija instrukcija i source
        self.codemem = []   # lista {'inst', 'type', 'operands': [(kind,reg,data),...]}
        self.symtab  = []   # lista {'name', 'address', 'sym_type': 'data'|'jump'}
        self.source  = []   # lista {'text', 'address': code_index}
        self.sim_error = None

    # Memorija

    def getmem(self, address):
        """Čita int32 sa adrese (kao word* getmem u hipsim)"""
        if address < 0 or address + 3 >= MEM_SIZE:
            raise SimError(f"Adresa izvan opsega memorije: {address}")
        return struct.unpack_from('<i', self.datamem, address)[0]

    def setmem(self, address, value):
        """Upisuje int32 na adresu"""
        if address < 0 or address + 3 >= MEM_SIZE:
            raise SimError(f"Adresa izvan opsega memorije: {address}")
        struct.pack_into('<i', self.datamem, address, _to_word(value) & 0xFFFFFFFF)

    # Operandi

    def get_operand(self, op):
        """Čita vrednost operanda (get_operand iz simulator.c)"""
        kind, reg, data = op
        if kind == OP_REGISTER:
            return self.reg[reg]
        elif kind == OP_INDIRECT:
            return self.getmem(self.reg[reg])
        elif kind == OP_INDEX:
            return self.getmem(self.reg[reg] + data)
        elif kind == OP_CONSTANT:
            return data
        elif kind == OP_ADDRESS:
            return data
        elif kind == OP_DATA:
            return self.getmem(self.symtab[data]['address'])
        raise SimError(f"Nepoznata vrsta operanda: {kind}")

    def set_operand(self, op, value):
        """Upisuje vrednost operanda (set_operand iz simulator.c)"""
        kind, reg, data = op
        v = _to_word(value)
        if kind == OP_REGISTER:
            self.reg[reg] = v
        elif kind == OP_INDIRECT:
            self.setmem(self.reg[reg], v)
        elif kind == OP_INDEX:
            self.setmem(self.reg[reg] + data, v)
        elif kind == OP_DATA:
            self.setmem(self.symtab[data]['address'], v)

    def _label_addr(self, op):
        """Adresa labele za skokove/call (direktno iz symtab kao u hipsim run_once)"""
        kind, reg, data = op
        if kind == OP_DATA:
            return self.symtab[data]['address']
        return data

    # Indikatori

    def set_flags_signed(self, result):
        """set_flags_signed iz simulator.c — result je Python int (int64)"""
        self.zero     = 1 if result == 0 else 0
        self.sign     = 1 if (result & 0x80000000) != 0 else 0
        self.carry    = 0
        self.overflow = 1 if (result > 2147483647 or result < -2147483648) else 0

    def set_flags_unsigned(self, result):
        """set_flags_unsigned iz simulator.c — result je Python int (uint64)"""
        result = _to_uint64(result)
        self.zero     = 1 if result == 0 else 0
        self.sign     = 1 if (result & 0x80000000) != 0 else 0
        self.carry    = 1 if result > 0xFFFFFFFF else 0
        self.overflow = 0

    # Izvrsavanje jedne instrukcije

    def run_once(self):
        """run_once iz simulator.c — identična logika"""
        if self.halt:
            return
        if self.pc < 0 or self.pc >= len(self.codemem):
            self.halt = True
            return

        inst  = self.codemem[self.pc]
        icode = inst['inst']
        itype = inst['type']
        op    = inst['operands']

        if icode == INS_HALT:
            self.halt = True

        elif icode == INS_PUSH:
            self.reg[STACK_POINTER] -= 4
            self.setmem(self.reg[STACK_POINTER], self.get_operand(op[0]))
            self.pc += 1

        elif icode == INS_POP:
            self.set_operand(op[0], self.getmem(self.reg[STACK_POINTER]))
            self.reg[STACK_POINTER] += 4
            self.pc += 1

        elif icode == INS_CALL:
            self.reg[STACK_POINTER] -= 4
            self.setmem(self.reg[STACK_POINTER], self.pc + 1)
            self.pc = self._label_addr(op[0])

        elif icode == INS_RET:
            self.pc = self.getmem(self.reg[STACK_POINTER])
            self.reg[STACK_POINTER] += 4

        elif icode == INS_CMP:
            a = self.get_operand(op[0])
            b = self.get_operand(op[1])
            if itype == SIGNED_TYPE:
                self.set_flags_signed(a - b)
            else:
                self.set_flags_unsigned(_to_uint64((a & 0xFFFFFFFF) - (b & 0xFFFFFFFF)))
            self.pc += 1

        elif icode == INS_JMP:
            self.pc = self._label_addr(op[0])
        elif icode == INS_JEQ:
            self.pc = self._label_addr(op[0]) if self.zero else self.pc + 1
        elif icode == INS_JNE:
            self.pc = self._label_addr(op[0]) if not self.zero else self.pc + 1

        elif icode == INS_JGT:
            if itype == SIGNED_TYPE:
                cond = (not bool(self.sign ^ self.overflow)) and (not bool(self.zero))
            else:
                cond = (not bool(self.carry)) and (not bool(self.zero))
            self.pc = self._label_addr(op[0]) if cond else self.pc + 1

        elif icode == INS_JLT:
            if itype == SIGNED_TYPE:
                cond = bool(self.sign ^ self.overflow)
            else:
                cond = bool(self.carry)
            self.pc = self._label_addr(op[0]) if cond else self.pc + 1

        elif icode == INS_JGE:
            if itype == SIGNED_TYPE:
                cond = not bool(self.sign ^ self.overflow)
            else:
                cond = not bool(self.carry)
            self.pc = self._label_addr(op[0]) if cond else self.pc + 1

        elif icode == INS_JLE:
            if itype == SIGNED_TYPE:
                cond = bool((self.sign ^ self.overflow) | self.zero)
            else:
                cond = bool(self.carry | self.zero)
            self.pc = self._label_addr(op[0]) if cond else self.pc + 1

        elif icode == INS_JC:
            self.pc = self._label_addr(op[0]) if self.carry else self.pc + 1
        elif icode == INS_JNC:
            self.pc = self._label_addr(op[0]) if not self.carry else self.pc + 1
        elif icode == INS_JO:
            self.pc = self._label_addr(op[0]) if self.overflow else self.pc + 1
        elif icode == INS_JNO:
            self.pc = self._label_addr(op[0]) if not self.overflow else self.pc + 1

        elif icode in (INS_ADD, INS_SUB, INS_MUL, INS_DIV):
            a = self.get_operand(op[0])
            b = self.get_operand(op[1])
            if itype == SIGNED_TYPE:
                if icode == INS_ADD:   result = a + b
                elif icode == INS_SUB: result = a - b
                elif icode == INS_MUL: result = a * b
                elif icode == INS_DIV:
                    if b == 0: raise SimError("Deljenje nulom")
                    result = int(a / b)  # truncation toward zero like C
                self.set_operand(op[2], result)
                self.set_flags_signed(result)
            else:
                ua = a & 0xFFFFFFFF; ub = b & 0xFFFFFFFF
                if icode == INS_ADD:   result = ua + ub
                elif icode == INS_SUB: result = _to_uint64(ua - ub)
                elif icode == INS_MUL: result = ua * ub
                elif icode == INS_DIV:
                    if ub == 0: raise SimError("Deljenje nulom")
                    result = ua // ub
                self.set_operand(op[2], result)
                self.set_flags_unsigned(result)
            self.pc += 1

        elif icode == INS_MOV:
            self.set_operand(op[1], self.get_operand(op[0]))
            self.pc += 1

    # Stanje za JSON odgovor

    def get_state(self):
        """Vraća kompletno stanje simulatora za frontend"""
        # Source linije sa PC markerom
        source_lines = []
        for i, s in enumerate(self.source):
            source_lines.append({
                'line_num': i + 1,
                'text': s['text'],
                'address': s['address'],
                'is_pc': (s['address'] == self.pc 
                        and not self.halt
                        and (i + 1 >= len(self.source) or self.source[i + 1]['address'] != s['address']))
            })

        # Globalne promenljive (WORD deklaracije iz ASM-a)
        globals_list = [
            {
                'name':    sym['name'],
                'address': sym['address'],
                'value':   self.getmem(sym['address'])
            }
            for sym in self.symtab if sym['sym_type'] == 'data'
        ]

        # Stek: od SP navise (kao u print_stack)
        stack_entries = []
        sp = self.reg[STACK_POINTER]
        fp = self.reg[FRAME_POINTER]
        top = min(sp + 9 * 4, MEM_SIZE - 4)  # prikaži max 10 elemenata (4-byte poravnanje)
        for addr in range(top, sp - 1, -4):
            if addr < 0 or addr + 3 >= MEM_SIZE:
                continue
            try:
                val = self.getmem(addr)
            except SimError:
                break
            entry = {
                'address':   addr,
                'value':     val,
                'is_top':    addr == sp,
                'is_fp':     addr == fp,
                'fp_offset': addr - fp if fp >= sp else None
            }
            stack_entries.append(entry)

        return {
            'source_lines': source_lines,
            'registers': {
                'pc':    self.pc,
                'reg':   self.reg[:],
                'flags': {'Z': self.zero, 'S': self.sign,
                           'C': self.carry, 'O': self.overflow}
            },
            'globals':   globals_list,
            'stack':     stack_entries,
            'halted':    self.halt,
            'exit_code': self.reg[FUNCTION_REGISTER] if self.halt else None
        }


# Parser ASM fajla

def _parse_operand(token, symtab, label_map):
    """
    Parsira jedan operand tokena iz micko output.asm.
    label_map: {label_name → symtab_index}
    """
    token = token.strip()
    if not token:
        return None

    # Registar: %N
    m = re.match(r'^%(\d+)$', token)
    if m:
        return (OP_REGISTER, int(m.group(1)), 0)

    # Konstanta: $[+-]?N
    m = re.match(r'^\$([+-]?\d+)$', token)
    if m:
        return (OP_CONSTANT, 0, int(m.group(1)))

    # Indeksno: [+-]?N(%M) — npr. -4(%14) ili 8(%14)
    m = re.match(r'^([+-]?\d+)\(%(\d+)\)$', token)
    if m:
        return (OP_INDEX, int(m.group(2)), int(m.group(1)))

    # Indirektno: (%M)
    m = re.match(r'^\(%(\d+)\)$', token)
    if m:
        return (OP_INDIRECT, int(m.group(1)), 0)

    # Labela: @fun_exit ili fun (za CALL/JMP)
    if token in label_map:
        return (OP_DATA, 0, label_map[token])

    return None


def _parse_instruction(line, label_map):
    """Parsira jednu instrukciju iz ASM linije."""
    line = line.strip()
    if not line:
        return None

    # Razdvoji mnemonic od operanada
    m = re.match(r'^(\w+)\s*(.*)', line)
    if not m:
        return None

    mnemonic = m.group(1).upper()
    ops_str  = m.group(2).strip()

    if mnemonic not in INST_MAP:
        return None

    inst_code, inst_type = INST_MAP[mnemonic]

    # Parsiranje operanada (razdeljeni zarezima)
    operands = []
    if ops_str:
        for tok in ops_str.split(','):
            op = _parse_operand(tok.strip(), None, label_map)
            if op is not None:
                operands.append(op)

    return {'inst': inst_code, 'type': inst_type, 'operands': operands}


def parse_asm(asm_text):
    """
    Parsira micko output.asm i vraća inicijalizovani Simulator.
    Dodaje isti entry code koji hipsim dodaje:
        HALT  (guard)
        PUSH $0
        CALL main
        HALT
    Vraca (sim, error_string_or_None).
    """
    sim = Simulator()

    # Razbijamo na linije, uklanjamo prazne i komentare
    raw_lines = asm_text.split('\n')
    lines = []
    for rl in raw_lines:
        stripped = rl.strip()
        if stripped and not stripped.startswith('#'):
            lines.append(stripped)

    # Prolaz 1: identifikuj stavke (labela, WORD, instrukcija)
    items = []  # ('label', name) | ('word', name, count) | ('instr', text)
    for line in lines:
        # WORD deklaracija: "name: WORD N"
        m = re.match(r'^(@?[\w]+):\s+WORD\s+(\d+)\s*$', line, re.IGNORECASE)
        if m:
            items.append(('word', m.group(1), int(m.group(2))))
            continue

        # Definicija labele: "name:"
        m = re.match(r'^(@?[\w]+):\s*$', line)
        if m:
            items.append(('label', m.group(1)))
            continue

        # Instrukcija
        items.append(('instr', line))

    # Prolaz 2: izgradi label → address mapu (pre-scan)
    label_to_addr = {}   # label_name → code_index (ili data_addr)
    data_cnt  = 0
    code_cnt  = 0

    for item in items:
        if item[0] == 'label':
            label_to_addr[item[1]] = code_cnt
        elif item[0] == 'word':
            name  = item[1]
            count = item[2]
            label_to_addr[name] = data_cnt
            sim.symtab.append({
                'name':     name,
                'address':  data_cnt,
                'sym_type': 'data'
            })
            # Nuluj podatke u memoriji (data segment)
            for b in range(count * 4):
                sim.datamem[data_cnt + b] = 0
            data_cnt += count * 4
        elif item[0] == 'instr':
            code_cnt += 1

    # Prolaz 3: popuni symtab za labele (jump targets)
    label_map = {}  # label_name → symtab_index
    # Prvo data simboli (vec ubaceni)
    for i, sym in enumerate(sim.symtab):
        label_map[sym['name']] = i

    # Dodaj jump labele
    for lname, laddr in label_to_addr.items():
        if lname not in label_map:
            idx = len(sim.symtab)
            sim.symtab.append({'name': lname, 'address': laddr, 'sym_type': 'jump'})
            label_map[lname] = idx
        else:
            # Azuriraj adresu ako je vec u tabeli
            sim.symtab[label_map[lname]]['address'] = laddr

    # Prolaz 4: generiši instrukcije i source linije
    code_idx = 0
    for item in items:
        if item[0] == 'label':
            sim.source.append({'text': item[1] + ':', 'address': code_idx})
        elif item[0] == 'word':
            pass  # data segment, vec obradjeno
        elif item[0] == 'instr':
            text = item[1]
            sim.source.append({'text': '\t' + text, 'address': code_idx})
            inst = _parse_instruction(text, label_map)
            if inst is None:
                return None, f"Greška pri parsiranju instrukcije: '{text}'"
            sim.codemem.append(inst)
            code_idx += 1

    # Entry code (identičan kao add_entry_code u simulator.c)
    # HALT (guard)
    sim.source.append({'text': '\tHALT', 'address': code_idx})
    sim.codemem.append({'inst': INS_HALT, 'type': NO_TYPE, 'operands': []})
    code_idx += 1

    # PC startuje ovde (PUSH $0) — kao processor.pc = code_cnt u hipsim
    sim.pc = code_idx

    # PUSH $0
    sim.source.append({'text': '\tPUSH $0', 'address': code_idx})
    sim.codemem.append({'inst': INS_PUSH, 'type': NO_TYPE,
                        'operands': [(OP_CONSTANT, 0, 0)]})
    code_idx += 1

    # CALL main
    main_idx = label_map.get('main')
    if main_idx is None:
        return None, "ASM fajl ne sadrži labelu 'main'"
    sim.source.append({'text': '\tCALL main', 'address': code_idx})
    sim.codemem.append({'inst': INS_CALL, 'type': NO_TYPE,
                        'operands': [(OP_DATA, 0, main_idx)]})
    code_idx += 1

    # HALT (kraj)
    sim.source.append({'text': '\tHALT', 'address': code_idx})
    sim.codemem.append({'inst': INS_HALT, 'type': NO_TYPE, 'operands': []})

    return sim, None
