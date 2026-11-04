#!/usr/bin/env python3
"""S0: motor, gear and current-limit sizing for the balancing robot.

Model
  The planar body/wheel model of e-inverted-pendulum/documentation/theory/pendulum-dynamics.md,
  extended with the motor rotors' inertia reflected through the gearbox. Rotor speed is
  G * (x_dot / r - theta_dot) because the motor stator is fixed to the body. Rotor kinetic energy
  1/2 * J_R * (x_dot / r - theta_dot)^2, with J_R = 2 * J_rotor * G^2, adds:
      M_xx += J_R / r^2,  M_xtheta -= J_R / r,  M_thetatheta += J_R.
  Each motor is a brushed DC machine driven by bridge voltage (the firmware maps effort to duty,
  motion-actuation.md Part C). Current is clipped at the DRV8711 trip current. Inductance is
  ignored here: tau_e ~ 0.1-0.3 ms is far below the ~0.1 s fall time constant.
  Control is a discrete LQR at 500 Hz (REQ-RT-001) with a one-sample computation delay
  (REQ-RT-004), designed on the delay-augmented ZOH model.

Checks
  - recovery from a 10 deg displacement: back within 3 deg in 1 s, never past 35 deg
    (REQ-CTRL-002, REQ-SAFE-002);
  - largest recoverable displacement (target >= 2 x 10 deg);
  - duty headroom when cruising at 1.0 m/s (commanded limit) and 1.5 m/s (design limit,
    wheel-odometry.md:104);
  - DRV8711 TORQUE/ISGAIN for the chosen Rsense (Drv8711DriverConfiguration.cpp:10-19);
  - PWM current ripple at 25 kHz (REQ-DRIVE-007) and encoder edge rates.

Every input is in MOTORS, GEARS, ELECTRICAL or mechanical/mass_budget.csv, with its source.
Run: python3 simulation/sizing.py -> simulation/results/sizing_*.{csv,json}, simulation/plots/sizing_*.png
"""

import csv
import json
import math
import pathlib

import numpy as np
from scipy.linalg import expm, solve_discrete_are

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "simulation" / "results"
PLOTS = ROOT / "simulation" / "plots"
GRAVITY = 9.81

MOTORS = {
    "6000rpm": {
        "source": "JGA25-370 12 V listings: 1:21.3 -> 280 rpm / 1:35 -> 170 rpm no-load, I0 60 mA, stall 1.3 A",
        "v_rated": 12.0, "rpm_no_load": 6000.0, "i_no_load": 0.060, "i_stall": 1.30,
        "j_rotor": 1.5e-6, "inductance": 1.5e-3, "i_rated": 0.45,
    },
    "4300rpm": {
        "source": "JGA25-371 12 V encoder variant: 1:34 -> 126 rpm, I0 46 mA, stall 1.0 A",
        "v_rated": 12.0, "rpm_no_load": 4284.0, "i_no_load": 0.046, "i_stall": 1.00,
        "j_rotor": 1.5e-6, "inductance": 2.0e-3, "i_rated": 0.35,
    },
}
J_ROTOR_SOURCE = "ASSUMPTION 370-size rotor inertia 1.5e-6 kg m^2 (measure by spin-down)"
INDUCTANCE_SOURCE = "ASSUMPTION 1-3 mH (measure with an LCR meter at bring-up)"
GEARS = [4.4, 9.6, 20.4, 34.0, 46.8]
GEAR_EFFICIENCY = {"low": 0.35, "nominal": 0.45}
EFFICIENCY_SOURCE = "derived: listed stall torque / (Kt * I_stall * G) = 0.35-0.50 across listings"

ELECTRICAL = {
    "vbat": {"full": 12.6, "nominal": 11.1, "arm_min": 9.9},
    "rsense": 0.050,
    "drv_vref": 2.75,
    "isgain": [40, 20, 10, 5],
    "pwm_hz": 25_000.0,
    "encoder_lines": [100, 250, 500, 1000],
}

CONTROL = {"period": 0.002, "theta_max": math.radians(2.0), "rate_max": 0.5,
           "x_max": 0.5, "v_max": 0.5, "voltage_fraction": 0.3}


def read_mass_budget(path=ROOT / "mechanical" / "mass_budget.csv"):
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def body_parameters(rows=None):
    rows = read_mass_budget() if rows is None else rows
    axle = next(row for row in rows if row["shape"] == "axle")
    axle_z, axle_y = float(axle["z_mm"]) / 1000.0, float(axle["y_mm"]) / 1000.0
    mass = moment_z = moment_y = inertia = 0.0
    wheel_mass = wheel_inertia = wheel_radius = 0.0
    for row in rows:
        if row["shape"] == "axle":
            continue
        qty, m = int(row["qty"]), float(row["mass_g"]) / 1000.0
        z = float(row["z_mm"]) / 1000.0 - axle_z
        y = float(row["y_mm"]) / 1000.0 - axle_y
        h, d = float(row["height_mm"]) / 1000.0, float(row["depth_mm"]) / 1000.0
        if row["shape"] == "wheel":
            wheel_radius = h / 2.0
            wheel_mass += qty * m
            wheel_inertia = 0.6 * m * wheel_radius ** 2
            continue
        own = {"plate": m * h ** 2 / 12.0, "box": m * (h ** 2 + d ** 2) / 12.0,
               "cylinder": 0.5 * m * (h / 2.0) ** 2}.get(row["shape"], 0.0)
        mass += qty * m
        moment_z += qty * m * z
        moment_y += qty * m * y
        inertia += qty * (own + m * (z ** 2 + y ** 2))
    com_z, com_y = moment_z / mass, moment_y / mass
    length = math.hypot(com_z, com_y)
    return {
        "m": mass, "l": length, "J": inertia - mass * length ** 2,
        "M": wheel_mass, "Jw": wheel_inertia, "r": wheel_radius,
        "com_y_mm": com_y * 1000.0,
        "lean_deg": math.degrees(math.atan2(com_y, com_z)),
    }


def battery_side_variants(battery_item="battery_3s_1000mah", plate_half=0.8):
    rows = read_mass_budget()
    battery = next(row for row in rows if row["item"] == battery_item)
    depth = float(battery["depth_mm"])
    variants = {}
    for side, y in (("top_side", -(plate_half + depth / 2.0)), ("bottom_side", plate_half + depth / 2.0)):
        moved = [dict(row, y_mm=str(y)) if row is battery else row for row in rows]
        body = body_parameters(moved)
        variants[side] = {"battery_y_mm": y, "l_mm": body["l"] * 1000.0,
                          "com_y_mm": body["com_y_mm"], "lean_deg": body["lean_deg"]}
    return variants


def motor_constants(motor):
    resistance = motor["v_rated"] / motor["i_stall"]
    omega0 = motor["rpm_no_load"] * 2 * math.pi / 60.0
    ke = (motor["v_rated"] - motor["i_no_load"] * resistance) / omega0
    return {"R": resistance, "Ke": ke, "Kt": ke, "Tf": ke * motor["i_no_load"]}


class Robot:
    def __init__(self, body, motor, gear, efficiency, i_trip):
        self.b, self.motor, self.G, self.eta, self.i_trip = body, motor, gear, efficiency, i_trip
        self.k = motor_constants(motor)
        self.JR = 2.0 * motor["j_rotor"] * gear ** 2

    def wheel_torque(self, voltage, x_dot, theta_dot):
        omega_m = self.G * (x_dot / self.b["r"] - theta_dot)
        current = np.clip((voltage - self.k["Ke"] * omega_m) / self.k["R"], -self.i_trip, self.i_trip)
        friction = self.G * self.k["Tf"] * math.tanh(omega_m / 5.0)
        return 2.0 * (self.G * self.eta * self.k["Kt"] * current - friction), current, omega_m

    def derivative(self, state, voltage):
        theta, theta_dot, x, x_dot = state
        b = self.b
        torque, _, _ = self.wheel_torque(voltage, x_dot, theta_dot)
        mxx = b["M"] + b["m"] + 2 * b["Jw"] / b["r"] ** 2 + self.JR / b["r"] ** 2
        mxt = b["m"] * b["l"] * math.cos(theta) - self.JR / b["r"]
        mtt = b["J"] + b["m"] * b["l"] ** 2 + self.JR
        rhs_x = torque / b["r"] + b["m"] * b["l"] * theta_dot ** 2 * math.sin(theta)
        rhs_t = -torque + b["m"] * GRAVITY * b["l"] * math.sin(theta)
        det = mxx * mtt - mxt ** 2
        x_dd = (mtt * rhs_x - mxt * rhs_t) / det
        t_dd = (mxx * rhs_t - mxt * rhs_x) / det
        return np.array([theta_dot, t_dd, x_dot, x_dd])

    def linear_model(self):
        eps = 1e-6
        a = np.zeros((4, 4))
        for i in range(4):
            dz = np.zeros(4)
            dz[i] = eps
            a[:, i] = (self.derivative(dz, 0.0) - self.derivative(-dz, 0.0)) / (2 * eps)
        b = ((self.derivative(np.zeros(4), eps) - self.derivative(np.zeros(4), -eps)) / (2 * eps)).reshape(4, 1)
        return a, b

    def controller(self, vbat):
        a, b = self.linear_model()
        period = CONTROL["period"]
        n = 4
        block = np.zeros((n + 1, n + 1))
        block[:n, :n], block[:n, n:] = a * period, b * period
        phi = expm(block)
        ad, bd = phi[:n, :n], phi[:n, n:]
        aa = np.block([[ad, bd], [np.zeros((1, n)), np.zeros((1, 1))]])
        ba = np.vstack([np.zeros((n, 1)), np.ones((1, 1))])
        q = np.diag([1 / CONTROL["theta_max"] ** 2, 1 / CONTROL["rate_max"] ** 2,
                     1 / CONTROL["x_max"] ** 2, 1 / CONTROL["v_max"] ** 2, 0.0])
        r = np.array([[1.0 / (CONTROL["voltage_fraction"] * vbat) ** 2]])
        p = solve_discrete_are(aa, ba, q, r)
        return np.linalg.solve(r + ba.T @ p @ ba, ba.T @ p @ aa)

    def simulate(self, theta0_deg, vbat, gain, duration=3.0, substeps=4):
        period = CONTROL["period"]
        dt = period / substeps
        state = np.array([math.radians(theta0_deg), 0.0, 0.0, 0.0])
        applied = 0.0
        trace = {"t": [], "theta": [], "voltage": [], "current": [], "omega_m": []}
        fell, last_outside = False, 0.0
        for step in range(int(duration / period)):
            command = float(np.clip(-(gain @ np.append(state, applied))[0], -vbat, vbat))
            for _ in range(substeps):
                k1 = self.derivative(state, applied)
                k2 = self.derivative(state + 0.5 * dt * k1, applied)
                k3 = self.derivative(state + 0.5 * dt * k2, applied)
                k4 = self.derivative(state + dt * k3, applied)
                state = state + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
            t = (step + 1) * period
            _, current, omega_m = self.wheel_torque(applied, state[3], state[1])
            trace["t"].append(t)
            trace["theta"].append(math.degrees(state[0]))
            trace["voltage"].append(applied)
            trace["current"].append(float(current))
            trace["omega_m"].append(omega_m)
            if abs(state[0]) > math.radians(35.0):
                fell = True
                break
            if abs(state[0]) > math.radians(3.0):
                last_outside = t
            applied = command
        settled = not fell and abs(trace["theta"][-1]) < 3.0
        return {
            "fell": fell, "settled": settled, "settle_time": last_outside if settled else None,
            "peak_current": max(map(abs, trace["current"])),
            "peak_duty": max(map(abs, trace["voltage"])) / vbat,
            "peak_motor_rpm": max(map(abs, trace["omega_m"])) * 60 / (2 * math.pi),
            "trace": trace,
        }

    def recoverable_angle(self, vbat, gain):
        low, high = 1.0, 34.0
        if not self.simulate(low, vbat, gain)["settled"]:
            return 0.0
        for _ in range(8):
            mid = 0.5 * (low + high)
            low, high = (mid, high) if self.simulate(mid, vbat, gain)["settled"] else (low, mid)
        return low

    def cruise_duty(self, speed, vbat):
        omega_m = self.G * speed / self.b["r"]
        return (self.k["Ke"] * omega_m + self.k["R"] * self.motor["i_no_load"]) / vbat


def drv8711_setting(i_trip, rsense):
    for isgain in ELECTRICAL["isgain"]:
        torque = round(256 * isgain * rsense * i_trip / ELECTRICAL["drv_vref"])
        if torque <= 255:
            return {"isgain": isgain, "torque": torque,
                    "actual_trip": ELECTRICAL["drv_vref"] * torque / (256 * isgain * rsense)}
    return None


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    body = body_parameters()
    tau = math.sqrt((body["J"] + body["m"] * body["l"] ** 2) / (body["m"] * GRAVITY * body["l"]))
    print(f"body: m={body['m']:.3f} kg  l={body['l'] * 1000:.1f} mm  J={body['J']:.2e} kg m^2  "
          f"M={body['M']:.3f} kg  Jw={body['Jw']:.2e}  r={body['r'] * 1000:.0f} mm  "
          f"lean={body['lean_deg']:.1f} deg  tau={tau * 1000:.0f} ms")

    rows = []
    for motor_name, motor in MOTORS.items():
        for gear in GEARS:
            for eta_name, eta in GEAR_EFFICIENCY.items():
                for limit_name, i_trip in (("rated", motor["i_rated"]), ("stall", motor["i_stall"])):
                    for v_name, vbat in ELECTRICAL["vbat"].items():
                        robot = Robot(body, motor, gear, eta, i_trip)
                        gain = robot.controller(vbat)
                        run = robot.simulate(10.0, vbat, gain)
                        rows.append({
                            "motor": motor_name, "gear": gear, "efficiency": eta_name,
                            "current_limit": limit_name, "i_trip": i_trip, "vbat": vbat, "vbat_case": v_name,
                            "reflected_inertia": robot.JR,
                            "recover_10deg": run["settled"] and run["settle_time"] <= 1.0,
                            "settle_time_10deg": run["settle_time"],
                            "peak_current_10deg": run["peak_current"],
                            "peak_duty_10deg": run["peak_duty"],
                            "max_recoverable_deg": robot.recoverable_angle(vbat, gain),
                            "duty_1p0_mps": robot.cruise_duty(1.0, vbat),
                            "duty_1p5_mps": robot.cruise_duty(1.5, vbat),
                        })

    with open(RESULTS / "sizing_sweep.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def worst(motor, gear, limit):
        cases = [r for r in rows if r["motor"] == motor and r["gear"] == gear and r["current_limit"] == limit]
        return {
            "all_recover_10deg": all(r["recover_10deg"] for r in cases),
            "min_recoverable_deg": min(r["max_recoverable_deg"] for r in cases),
            "max_duty_1p0_at_arm_min": max(r["duty_1p0_mps"] for r in cases if r["vbat_case"] == "arm_min"),
            "max_duty_1p5_at_arm_min": max(r["duty_1p5_mps"] for r in cases if r["vbat_case"] == "arm_min"),
            "max_peak_current": max(r["peak_current_10deg"] for r in cases),
        }

    def passes(w):
        return (w["all_recover_10deg"] and w["min_recoverable_deg"] >= 20.0
                and w["max_duty_1p0_at_arm_min"] <= 0.70)

    summary = {"body": body, "tau_s": tau, "per_config": {}}
    print(f"\n{'motor':>8} {'gear':>5} {'limit':>6} {'10deg ok':>8} {'min recov':>9} {'duty@1.0':>8} {'duty@1.5':>8} {'Ipk':>5} pass")
    candidates = []
    for motor in MOTORS:
        for gear in GEARS:
            for limit in ("rated", "stall"):
                w = worst(motor, gear, limit)
                w["pass"] = passes(w)
                summary["per_config"][f"{motor}_1:{gear}_{limit}"] = w
                if w["pass"] and limit == "stall":
                    rated = summary["per_config"][f"{motor}_1:{gear}_rated"]["min_recoverable_deg"]
                    candidates.append((motor, gear, w["min_recoverable_deg"], rated))
                print(f"{motor:>8} {gear:5.1f} {limit:>6} {str(w['all_recover_10deg']):>8} {w['min_recoverable_deg']:8.1f}° "
                      f"{w['max_duty_1p0_at_arm_min']:8.2f} {w['max_duty_1p5_at_arm_min']:8.2f} {w['max_peak_current']:5.2f} {w['pass']}")

    chosen = max(candidates, key=lambda c: (round(c[2]), c[3])) if candidates else None
    summary["criteria"] = ("per motor winding, worst case over gear efficiency 0.35-0.45 and VBAT 9.9-12.6 V: "
                           "recover 10 deg within 1 s; >= 20 deg recoverable; duty at 1.0 m/s <= 0.70 at 9.9 V; "
                           "rank by recoverable angle at the stall trip, then at the rated-current limit "
                           "(the search stops at 34 deg, so several configurations can tie at the ceiling)")
    summary["candidates"] = [{"motor": m, "gear": g, "min_recoverable_deg": d, "min_recoverable_rated_deg": r}
                             for m, g, d, r in candidates]
    summary["lean_by_battery_side"] = battery_side_variants()
    summary["chosen"] = {"motor": chosen[0], "gear": chosen[1]} if chosen else None

    i_trip = max(m["i_stall"] for m in MOTORS.values())
    summary["drv8711"] = {"rsense": ELECTRICAL["rsense"], "i_trip": i_trip,
                          **drv8711_setting(i_trip, ELECTRICAL["rsense"]),
                          "rsense_power_w": i_trip ** 2 * ELECTRICAL["rsense"]}
    period = 1.0 / ELECTRICAL["pwm_hz"]
    summary["pwm_ripple_pp_a"] = {
        f"L={m['inductance'] * 1e3:.1f}mH": ELECTRICAL["vbat"]["full"] * period / (4 * m["inductance"])
        for m in MOTORS.values()}
    motor_rev_s = max(m["rpm_no_load"] for m in MOTORS.values()) / 60.0 * ELECTRICAL["vbat"]["full"] / 12.0
    summary["encoder"] = {"max_motor_rev_s": motor_rev_s, "channel_hz_by_lines": {
        n: n * motor_rev_s for n in ELECTRICAL["encoder_lines"]}}
    summary["sources"] = {"motors": {k: v["source"] for k, v in MOTORS.items()},
                          "rotor_inertia": J_ROTOR_SOURCE, "inductance": INDUCTANCE_SOURCE,
                          "gear_efficiency": EFFICIENCY_SOURCE}

    with open(RESULTS / "sizing_summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=float)
    print(f"\ncandidates {summary['candidates']} -> chosen {summary['chosen']}")
    print(f"lean by battery side: {summary['lean_by_battery_side']}")
    print(f"DRV8711: {summary['drv8711']}")
    print(f"PWM ripple: {summary['pwm_ripple_pp_a']}")
    print(f"encoder channel frequency: {summary['encoder']}")

    if chosen:
        plot_recovery(body, chosen[0], chosen[1])


def plot_recovery(body, motor_name, gear):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(7, 7), sharex=True)
    for v_name, vbat in ELECTRICAL["vbat"].items():
        motor = MOTORS[motor_name]
        robot = Robot(body, motor, gear, GEAR_EFFICIENCY["low"], motor["i_stall"])
        run = robot.simulate(10.0, vbat, robot.controller(vbat))
        tr = run["trace"]
        axes[0].plot(tr["t"], tr["theta"], label=f"{vbat} V")
        axes[1].plot(tr["t"], np.array(tr["voltage"]) / vbat)
        axes[2].plot(tr["t"], tr["current"])
    axes[0].axhline(3, ls=":", c="grey")
    axes[0].axhline(-3, ls=":", c="grey")
    axes[0].set_ylabel("pitch (deg)")
    axes[1].set_ylabel("duty")
    axes[2].set_ylabel("motor current (A)")
    axes[2].set_xlabel("time (s)")
    axes[0].legend()
    axes[0].set_title(f"Recovery from 10 deg: {motor_name} motor, 1:{gear}, efficiency 0.35, I_trip = stall")
    fig.tight_layout()
    fig.savefig(PLOTS / "sizing_recovery.png", dpi=110)


if __name__ == "__main__":
    main()
