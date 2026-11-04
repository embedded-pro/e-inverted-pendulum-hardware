#!/usr/bin/env python3
"""Validate pin-data/pinmap.csv against the MCU package data and, optionally, the firmware.

Checks:
  1. every pin is bonded in the package (pin-data/stm32wb55rgvx_vfqfpn68.csv);
  2. every alternate function or ADC channel exists on its pin;
  3. no pin is assigned twice, except signals that deliberately share one net;
  4. EXTI line numbers are unique (EXTI lines are keyed by pin number across ports);
  5. with --firmware, every pin the firmware declares in targets/platform_implementations/st/
     appears at the same pin under the same symbol name, and no mapped firmware symbol is missing.

Usage: check_pinmap.py [--firmware ../e-inverted-pendulum]
Exit code 0 when every check passes.
"""

import argparse
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINMAP = ROOT / "pin-data" / "pinmap.csv"
PACKAGE = ROOT / "pin-data" / "stm32wb55rgvx_vfqfpn68.csv"
FIRMWARE_PIN = re.compile(r"(\w+)\{\s*hal::Port::([A-H]),\s*(\d+)\s*\}")


def load_package():
    with open(PACKAGE, encoding="utf-8") as handle:
        return {row["name"]: set(row["alternates"].split()) for row in csv.DictReader(handle)}


def load_pinmap():
    with open(PINMAP, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def firmware_pins(firmware: pathlib.Path):
    found = {}
    for source in sorted((firmware / "targets" / "platform_implementations" / "st").glob("*.hpp")):
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            for symbol, port, pin in FIRMWARE_PIN.findall(line):
                found[symbol] = (f"P{port}{pin}", f"{source.name}:{number}")
    return found


def check(firmware):
    package = load_package()
    rows = load_pinmap()
    errors = []

    for row in rows:
        pin, mode, function = row["pin"], row["mode"], row["function"]
        if pin not in package:
            errors.append(f"{row['signal']}: {pin} is not bonded in VFQFPN68")
            continue
        if mode in ("af", "adc") and function not in package[pin]:
            errors.append(f"{row['signal']}: {function} not available on {pin}")

    by_pin = {}
    for row in rows:
        by_pin.setdefault(row["pin"], []).append(row)
    for pin, users in by_pin.items():
        if len(users) > 1:
            errors.append(f"{pin} assigned to {', '.join(u['signal'] for u in users)}")

    exti = {}
    for row in rows:
        if row["mode"] == "exti":
            line = int(re.sub(r"\D", "", row["pin"]))
            if line in exti:
                errors.append(f"EXTI{line} used by both {exti[line]} and {row['signal']}")
            exti[line] = row["signal"]

    nets = {}
    for row in rows:
        nets.setdefault(row["net"], []).append(row["signal"])

    if firmware:
        declared = firmware_pins(firmware)
        mapped = {row["firmware_symbol"]: row for row in rows if row["firmware_symbol"]}
        for symbol, (pin, where) in declared.items():
            if symbol not in mapped:
                errors.append(f"firmware {symbol} ({pin}, {where}) has no row in pinmap.csv")
            elif mapped[symbol]["pin"] != pin:
                errors.append(f"firmware {symbol} is {pin} ({where}) but pinmap says {mapped[symbol]['pin']}")
        for symbol in mapped:
            if symbol not in declared:
                errors.append(f"pinmap firmware_symbol {symbol} not found in firmware")
        print(f"firmware: {len(declared)} declared pins cross-checked")

    print(f"pins: {len(rows)} signals on {len(by_pin)} pins, EXTI lines {sorted(exti)}")
    shared = {net: signals for net, signals in nets.items() if len(signals) > 1}
    for net, signals in shared.items():
        print(f"shared net {net}: {', '.join(signals)}")
    for error in errors:
        print(f"ERROR {error}")
    print("PASS" if not errors else f"FAIL ({len(errors)} errors)")
    return not errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--firmware", type=pathlib.Path)
    args = parser.parse_args()
    sys.exit(0 if check(args.firmware) else 1)


if __name__ == "__main__":
    main()
