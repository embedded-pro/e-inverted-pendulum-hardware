"""ngspice batch driver: write a netlist, run `ngspice -b`, read wrdata columns into numpy arrays."""

import pathlib
import subprocess

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
WORK = ROOT / "work"
MODELS = ROOT / "models"


def run(name, netlist, vectors, analysis, pspice=False, timeout=600):
    """Run one simulation and return {vector: array} plus the scale under "x"."""
    folder = WORK / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".spiceinit").write_text("set ngbehavior=ps\n" if pspice else "\n", encoding="utf-8")
    data = folder / "out.txt"
    control = ("\n.control\nset wr_singlescale\nset wr_vecnames\noption numdgt=7\n"
               f"{analysis}\nwrdata {data} {' '.join(vectors)}\nquit\n.endc\n.end\n")
    (folder / "circuit.cir").write_text(f"* {name}\n" + netlist + control, encoding="utf-8")
    result = subprocess.run(["ngspice", "-b", "-o", str(folder / "run.log"), "circuit.cir"], cwd=folder,
                            capture_output=True, text=True, timeout=timeout)
    if not data.exists():
        log = (folder / "run.log").read_text(errors="replace")[-3000:]
        raise RuntimeError(f"ngspice failed for {name}:\n{log}\n{result.stderr[-1000:]}")
    lines = data.read_text().splitlines()
    header = lines[0].split()
    table = np.loadtxt(lines[1:])
    if table.ndim == 1:
        table = table[None, :]
    out = {"x": table[:, 0]}
    for i, vec in enumerate(header[1:], start=1):
        out[vec] = table[:, i]
    return out


def include(*names):
    return "\n".join(f'.include "{MODELS / n}"' for n in names) + "\n"
