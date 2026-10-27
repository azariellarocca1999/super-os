#!/usr/bin/env python3
"""Bilingual strings and data for flash page 4 (periodic table, constants, Wikipedia, weather):
build/pstrings.inc (PS_xxx offsets), build/pstrings.z80 (tables + text), build/ptzx0.inc (periodic table ZX0 stream), build/consts_text.inc"""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
from gen_strings import clean

S = [
    ("PT_TITLE", "TABLA PERIODICA", "PERIODIC TABLE"), ("PT_HINT", "FLECHAS  ENTER=DETALLE", "ARROWS  ENTER=DETAIL"),
    ("CAT0", "ALCALINO", "ALKALI"), ("CAT1", "ALCALINOTERREO", "ALK. EARTH"), ("CAT2", "TRANSICION", "TRANSITION"),
    ("CAT3", "POSTTRANSIC.", "POST-TRANS."), ("CAT4", "METALOIDE", "METALLOID"), ("CAT5", "NO METAL", "NONMETAL"),
    ("CAT6", "HALOGENO", "HALOGEN"), ("CAT7", "GAS NOBLE", "NOBLE GAS"), ("CAT8", "LANTANIDO", "LANTHANIDE"), ("CAT9", "ACTINIDO", "ACTINIDE"),
    ("F_MASS", "MASA", "MASS"), ("F_GROUP", "GRUPO", "GROUP"), ("F_PERIOD", "PERIODO", "PERIOD"), ("F_MELT", "FUSION K", "MELT K"),
    ("F_BOIL", "EBULL. K", "BOIL K"), ("F_EN", "ELECTRONEG.", "ELECTRONEG."), ("F_DENS", "DENSIDAD", "DENSITY"), ("F_CFG", "CONFIG.", "CONFIG."),
    ("CN_TITLE", "CONSTANTES", "CONSTANTS"), ("CN_HINT", "ENTER=A ANS", "ENTER=TO ANS"), ("CN_OK", "GUARDADA EN ANS", "STORED IN ANS"),
    ("WK_Q", "BUSCAR EN WIKIPEDIA", "SEARCH WIKIPEDIA"), ("WX_Q", "CIUDAD", "CITY"),
    ("WAIT", "ESPERANDO...", "WAITING..."), ("NOLINK", "SIN RESPUESTA ESP32", "NO ANSWER FROM ESP32"),
    ("ANYKEY", "PULSA UNA TECLA", "PRESS ANY KEY"),
]

# (symbol, name ES, name EN, value, unit)   CODATA 2022 / exact SI values
C = [
    ("c", "VELOCIDAD DE LA LUZ", "SPEED OF LIGHT", "299792458", "M/S"),
    ("G", "GRAVITACION UNIVERSAL", "GRAVITATIONAL CONST", "6.6743E-11", "M3/KG/S2"),
    ("h", "PLANCK", "PLANCK CONSTANT", "6.62607015E-34", "J S"),
    ("hbar", "PLANCK REDUCIDA", "REDUCED PLANCK", "1.054571817E-34", "J S"),
    ("e", "CARGA ELEMENTAL", "ELEMENTARY CHARGE", "1.602176634E-19", "C"),
    ("me", "MASA DEL ELECTRON", "ELECTRON MASS", "9.1093837139E-31", "KG"),
    ("mp", "MASA DEL PROTON", "PROTON MASS", "1.67262192595E-27", "KG"),
    ("mn", "MASA DEL NEUTRON", "NEUTRON MASS", "1.67492750056E-27", "KG"),
    ("u", "UNIDAD DE MASA ATOMICA", "ATOMIC MASS UNIT", "1.66053906892E-27", "KG"),
    ("NA", "AVOGADRO", "AVOGADRO", "6.02214076E23", "1/MOL"),
    ("kB", "BOLTZMANN", "BOLTZMANN", "1.380649E-23", "J/K"),
    ("R", "GASES IDEALES", "GAS CONSTANT", "8.314462618", "J/MOL/K"),
    ("F", "FARADAY", "FARADAY", "96485.33212", "C/MOL"),
    ("eps0", "PERMITIVIDAD VACIO", "VACUUM PERMITTIVITY", "8.8541878188E-12", "F/M"),
    ("mu0", "PERMEABILIDAD VACIO", "VACUUM PERMEABILITY", "1.25663706127E-6", "N/A2"),
    ("k", "COULOMB", "COULOMB CONSTANT", "8.9875517923E9", "N M2/C2"),
    ("sigma", "STEFAN-BOLTZMANN", "STEFAN-BOLTZMANN", "5.670374419E-8", "W/M2/K4"),
    ("b", "DESPLAZ. DE WIEN", "WIEN DISPLACEMENT", "2.897771955E-3", "M K"),
    ("alpha", "ESTRUCTURA FINA", "FINE STRUCTURE", "7.2973525643E-3", ""),
    ("Rinf", "RYDBERG", "RYDBERG", "10973731.568157", "1/M"),
    ("a0", "RADIO DE BOHR", "BOHR RADIUS", "5.29177210544E-11", "M"),
    ("muB", "MAGNETON DE BOHR", "BOHR MAGNETON", "9.2740100657E-24", "J/T"),
    ("muN", "MAGNETON NUCLEAR", "NUCLEAR MAGNETON", "5.0507837393E-27", "J/T"),
    ("re", "RADIO CLASICO ELECTRON", "CLASSICAL ELECTRON R", "2.8179403205E-15", "M"),
    ("lamC", "COMPTON ELECTRON", "COMPTON WAVELENGTH", "2.42631023538E-12", "M"),
    ("Eh", "HARTREE", "HARTREE ENERGY", "4.3597447222E-18", "J"),
    ("eV", "ELECTRONVOLT", "ELECTRONVOLT", "1.602176634E-19", "J"),
    ("g", "GRAVEDAD ESTANDAR", "STANDARD GRAVITY", "9.80665", "M/S2"),
    ("atm", "ATMOSFERA", "STANDARD ATMOSPHERE", "101325", "PA"),
    ("Vm", "VOLUMEN MOLAR STP", "MOLAR VOLUME STP", "0.02241396954", "M3/MOL"),
    ("KJ", "JOSEPHSON", "JOSEPHSON", "4.835978484E14", "HZ/V"),
    ("RK", "VON KLITZING", "VON KLITZING", "25812.80745", "OHM"),
    ("G0", "CUANTO CONDUCTANCIA", "CONDUCT. QUANTUM", "7.748091729E-5", "S"),
    ("lP", "LONGITUD DE PLANCK", "PLANCK LENGTH", "1.616255E-35", "M"),
    ("mP", "MASA DE PLANCK", "PLANCK MASS", "2.176434E-8", "KG"),
    ("tP", "TIEMPO DE PLANCK", "PLANCK TIME", "5.391247E-44", "S"),
    ("AU", "UNIDAD ASTRONOMICA", "ASTRONOMICAL UNIT", "1.495978707E11", "M"),
    ("ly", "ANO LUZ", "LIGHT YEAR", "9.4607304725808E15", "M"),
    ("pc", "PARSEC", "PARSEC", "3.0856775814914E16", "M"),
    ("Msun", "MASA DEL SOL", "SOLAR MASS", "1.98847E30", "KG"),
    ("Mearth", "MASA DE LA TIERRA", "EARTH MASS", "5.9722E24", "KG"),
    ("Rearth", "RADIO DE LA TIERRA", "EARTH RADIUS", "6.371E6", "M"),
    ("Rsun", "RADIO DEL SOL", "SOLAR RADIUS", "6.957E8", "M"),
    ("Mmoon", "MASA DE LA LUNA", "LUNAR MASS", "7.342E22", "KG"),
    ("vsnd", "SONIDO EN AIRE 20C", "SOUND IN AIR 20C", "343", "M/S"),
    ("T0", "CERO CELSIUS", "ZERO CELSIUS", "273.15", "K"),
    ("pi", "PI", "PI", "3.14159265359", ""),
    ("e_", "NUMERO DE EULER", "EULER NUMBER", "2.71828182846", ""),
    ("phi", "AUREO", "GOLDEN RATIO", "1.61803398875", ""),
]


def main():
    build = os.path.join(root, "build")
    os.makedirs(build, exist_ok=True)
    inc = ["; GENERATED by tools/gen_pstrings.py\n"]
    z = ["; GENERATED by tools/gen_pstrings.py\npstr_es:\n"]
    for i, (n, es, en) in enumerate(S):
        inc.append("PS_%-10s .equ %d\n" % (n, i * 2))
        z.append("    .dw ps_es_%d\n" % i)
    z.append("pstr_en:\n")
    for i, _ in enumerate(S):
        z.append("    .dw ps_en_%d\n" % i)
    for i, (n, es, en) in enumerate(S):
        z.append('ps_es_%d: .db "%s",0\n' % (i, clean(es).replace('"', "'")))
        z.append('ps_en_%d: .db "%s",0\n' % (i, clean(en).replace('"', "'")))
    open(os.path.join(build, "pstrings.inc"), "w").write("".join(inc))
    open(os.path.join(build, "pstrings.z80"), "w").write("".join(z))
    # constants: one record per line  sym|ES|EN|value|unit
    ct = ["; GENERATED by tools/gen_pstrings.py: constants (sym|name ES|name EN|value|unit)\nconst_text:\n"]
    for sym, es, en, val, unit in C:
        ct.append('    .db "%s|%s|%s|%s|%s",10\n' % (sym, es, en, val, unit))
    ct.append("    .db 0\n")
    open(os.path.join(build, "consts_text.inc"), "w").write("".join(ct))
    # periodic table stream
    data = open(os.path.join(build, "ptable.zx0"), "rb").read()
    pz = ["; GENERATED by tools/gen_pstrings.py: periodic table (ZX0)\npt_zx0:\n"]
    for i in range(0, len(data), 16):
        pz.append("    .db %s\n" % ",".join("$%02X" % b for b in data[i:i + 16]))
    open(os.path.join(build, "ptzx0.inc"), "w").write("".join(pz))
    print(len(S), "strings,", len(C), "constants,", len(data), "bytes of periodic table")


if __name__ == "__main__":
    main()
