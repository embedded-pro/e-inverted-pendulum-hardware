#!/usr/bin/env python3
"""Download the TI vendor models used by S4 into simulation/models/ti (gitignored: TI copyright, no
redistribution grant). TLV75533P: SBVM831 (unencrypted transient). TPS62933P: SLUM818 (unencrypted transient;
the TPS62933F used on the board has no unencrypted model, see REPORT.md S4 limits)."""

import io
import pathlib
import re
import urllib.request
import zipfile

TARGET = pathlib.Path(__file__).resolve().parent / "models" / "ti"
ZIPS = {"SBVM831": ["TLV75533P_TRANS.lib"],
        "SLUM818": ["TPS62933P_TRANS.lib", "TPS62933P_PSPICETransientModel_FeaturesandLimitations.pdf"]}


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for code, wanted in ZIPS.items():
        request = urllib.request.Request(f"https://www.ti.com/lit/zip/{code}",
                                         headers={"User-Agent": "e-inverted-pendulum-hardware/fetch_models"})
        archive = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(request, timeout=120).read()))
        for member in archive.namelist():
            name = pathlib.PurePosixPath(member).name
            if name in wanted:
                (TARGET / name).write_bytes(archive.read(member))
                print(f"{code}: {name}")
    source = (TARGET / "TLV75533P_TRANS.lib").read_text(errors="replace")
    helpers = set(re.findall(r"(?im)^\.subckt\s+(\w+)", source)) - {"TLV75533P_TRANS"}
    for helper in sorted(helpers, key=len, reverse=True):
        source = re.sub(rf"(?i)\b{re.escape(helper)}\b", f"{helper}_LDO", source)
    (TARGET / "TLV75533P_TRANS_ns.lib").write_text(source)
    print("namespaced TLV75533P helpers (both TI libraries define the same helper subcircuits)")


if __name__ == "__main__":
    main()
