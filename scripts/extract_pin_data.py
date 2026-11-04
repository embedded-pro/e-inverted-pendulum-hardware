#!/usr/bin/env python3
"""Extract the package pin list and alternate functions of an MCU from a KiCad symbol.

KiCad's STM32 symbols are generated from ST's STM32_open_pin_data, so the bonded pins of the
package and each pin's alternate functions come from ST's own database. The output CSV is
committed so the pin map check runs without KiCad installed.

Usage: extract_pin_data.py <library.kicad_sym> <symbol name> <out.csv>
"""

import csv
import re
import sys


def symbol_block(text: str, name: str) -> str:
    start = text.find(f'(symbol "{name}"')
    if start < 0:
        raise SystemExit(f"symbol {name} not found")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise SystemExit("unbalanced symbol block")


def pins(block: str):
    for match in re.finditer(r"\(pin (\w+) \w+", block):
        depth = 0
        for index in range(match.start(), len(block)):
            if block[index] == "(":
                depth += 1
            elif block[index] == ")":
                depth -= 1
                if depth == 0:
                    body = block[match.start():index + 1]
                    break
        name = re.search(r'\(name "([^"]*)"', body).group(1)
        number = re.search(r'\(number "([^"]*)"', body).group(1)
        alternates = re.findall(r'\(alternate "([^"]+)"', body)
        yield number, name, match.group(1), alternates


def main() -> None:
    library, name, out = sys.argv[1:4]
    block = symbol_block(open(library, encoding="utf-8").read(), name)
    rows = sorted(pins(block), key=lambda row: (len(row[0]), row[0]))
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["number", "name", "electrical_type", "alternates"])
        for number, pin_name, kind, alternates in rows:
            writer.writerow([number, pin_name, kind, " ".join(alternates)])
    print(f"{len(rows)} pins written to {out}")


if __name__ == "__main__":
    main()
