"""Shared helpers: operating assumptions, result writing and plotting."""

import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"

ASSUMPTIONS = {
    "battery_r_int": {"nominal": 0.060, "worst": 0.150, "source": "ASSUMPTION 3S 1000 mAh LiPo pack: 60 mOhm new, 150 mOhm cold/aged"},
    "battery_loop_l": {"value": 150e-9, "source": "ASSUMPTION ~15 cm XT30 lead pair"},
    "fuse_r": {"value": 0.035, "source": "1206FA-4A cold resistance 0.035 Ohm typ"},
    "mlcc_10u_25v_at_12v": {"value": 5e-6, "source": "ASSUMPTION Samsung CL21A106KAYNNNE DC-bias ~-50 % at 12 V"},
    "mlcc_22u_25v_at_5v": {"value": 13e-6, "source": "ASSUMPTION CL21A226MAQNNNE DC-bias ~-40 % at 5 V"},
    "motor_r": {"value": 9.2, "source": "S0: 12 V / 1.3 A stall (JGA25-370 6000 rpm winding)"},
    "motor_l": {"value": 1.5e-3, "source": "ASSUMPTION 1-3 mH (S0); measure at bring-up"},
    "motor_ke": {"value": 0.01833, "source": "S0 motor constant"},
    "logic_power": {"value": 1.56, "source": "docs/architecture.md: 5 V x 0.265 A / 0.85"},
}


def save(name, payload):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(payload, indent=2, default=float) + "\n", encoding="utf-8")


def figure(rows, title):
    fig, axes = plt.subplots(rows, 1, figsize=(8, 2.2 * rows + 0.6), sharex=True)
    if rows == 1:
        axes = [axes]
    axes[0].set_title(title)
    return fig, axes


def finish(fig, name):
    PLOTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(PLOTS / f"{name}.png", dpi=110)
    plt.close(fig)
