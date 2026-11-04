#!/usr/bin/env python3
"""Resolve the passive parts the schematic uses to JLCPCB parts and write bom/passives.json.

Resistors follow UniOhm's naming (0603WAF<code>T5E, 0402WGF<code>TCE). Capacitors and other
passives are listed by manufacturer part number. Each entry is looked up by MPN through the
JLC parts API; basic parts in stock are preferred and the result records library type and stock.

Usage: passive_catalog.py [--check]
"""

import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "bom" / "passives.json"
URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"

RESISTORS_0603 = ["0", "33", "100", "330", "1k", "1.5k", "2.2k", "4.7k", "5.1k", "10k", "22k", "27k",
                  "33k", "47k", "100k", "1M", "220", "470", "680", "2k", "3.3k", "15k", "20k", "56k", "68k",
                  "12k", "120k", "150k", "200k", "52.3k", "10.2k", "53.6k",
                  "240k", "270k", "300k", "36k", "39k", "43k", "51k", "62k", "82k", "91k"]
RESISTORS_0402 = ["0"]

CAPACITORS = {
    "100n_0402_16V_X7R": "CL05B104KO5NNNC",
    "100n_0603_50V_X7R": "CC0603KRX7R9BB104",
    "1u_0603_50V_X5R": "CL10A105KB8NNNC",
    "1u_0603_25V_X7R": "CL10B105KA8NNNC",
    "2.2u_0603_25V_X5R": "CL10A225KO8NNNC",
    "4.7u_0402_10V_X5R": "CL05A475MP5NRNC",
    "4.7u_0603_25V_X5R": "CL10A475KA8NNNC",
    "10u_0603_10V_X5R": "CL10A106KP8NNNC",
    "10u_0805_25V_X5R": "CL21A106KAYNNNE",
    "22u_0805_25V_X5R": "CL21A226MAQNNNE",
    "22u_0805_10V_X5R": "CL21A226MPQNNNE",
    "10n_0603_50V_X7R": "CL10B103KB8NNNC",
    "1n_0603_50V_X7R": "CL10B102KB8NNNC",
    "1n_0402_50V_C0G": "CL05C102JB5NNNC",
    "100p_0402_50V_C0G": "CL05C101JB5NNNC",
    "10p_0402_50V_C0G": "CL05C100JB5NNNC",
    "8p_0402_50V_C0G": "CL05C080CB5NNNC",
    "6.8p_0402_50V_C0G": "CL05C6R8CB5NNNC",
    "4.7n_0603_50V_X7R": "CL10B472KB8NNNC",
    "47n_0603_50V_X7R": "CL10B473KB8NNNC",
    "220n_0603_25V_X7R": "CL10B224KA8NNNC",
}


def resistor_mpn(value, package="0603"):
    multipliers = {"": 1, "k": 1e3, "M": 1e6}
    unit = value[-1] if value[-1] in "kM" else ""
    ohms = float(value[:-1] if unit else value) * multipliers[unit]
    if ohms == 0:
        code = "0000"
    elif ohms < 100:
        code = f"{round(ohms * 10):03d}J"
    else:
        exponent = 0
        while ohms >= 1000:
            ohms /= 10
            exponent += 1
        code = f"{round(ohms):03d}{exponent}"
    return f"0603WAF{code}T5E" if package == "0603" else f"0402WGF{code}TCE"


def search(mpn):
    body = json.dumps({"keyword": mpn, "currentPage": 1, "pageSize": 10}).encode()
    request = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "e-inverted-pendulum-hardware/passive_catalog"})
    items = json.load(urllib.request.urlopen(request, timeout=30))["data"]["componentPageInfo"]["list"] or []
    exact = [i for i in items if i["componentModelEn"].upper() == mpn.upper()]
    exact.sort(key=lambda i: (i["componentLibraryType"] != "base", -i["stockCount"]))
    return exact[0] if exact else None


def main():
    wanted = {f"R_{v}_0603": resistor_mpn(v) for v in RESISTORS_0603}
    wanted.update({f"R_{v}_0402": resistor_mpn(v, "0402") for v in RESISTORS_0402})
    wanted.update({f"C_{k}": mpn for k, mpn in CAPACITORS.items()})
    catalog, problems = {}, []
    for key, mpn in wanted.items():
        item = search(mpn)
        if item is None:
            problems.append(f"{key}: {mpn} not found")
            continue
        entry = {"mpn": mpn, "lcsc": item["componentCode"], "stock": item["stockCount"],
                 "library": "basic" if item["componentLibraryType"] == "base" else "extended",
                 "description": (item.get("describe") or "")[:100]}
        catalog[key] = entry
        if entry["stock"] < 1000:
            problems.append(f"{key}: low stock {entry['stock']}")
        print(f"{key:24} {mpn:22} {entry['lcsc']:>9} {entry['library']:8} {entry['stock']:>9}")
    OUT.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for problem in problems:
        print("WARN", problem)
    sys.exit(1 if problems and "--check" in sys.argv else 0)


if __name__ == "__main__":
    main()
