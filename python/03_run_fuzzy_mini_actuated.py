import argparse
import time
import traci
from fuzzy_controller import FuzzyExtender

TLS_ID = "C"

# Stop-line detektory (lanearea) – musíš ich mať v mini_additional.add.xml
DET_NS = "detNS"
DET_WE = "detWE"

# Incoming lane ID (z tvojho inspect_ids.py)
LANE_NS = "N2C_0"
LANE_WE = "W2C_0"

# Stabilnejšie parametre
MIN_GREEN = 12
MAX_GREEN = 90

# EXTEND (raz za green, rozhoduj X sekúnd pred switchom)
DECIDE_WHEN_REMAINING_LE = 5.0
MAX_EXT = 10

# Guardy pre extend (podľa CELÉHO pruhu – nie len stop-line detektora)
MIN_SERVED_LANE_VEH_FOR_EXT = 5      # odporúčam 3–8; pri d5 daj skôr 5
MAX_OTHER_LANE_HALT_FOR_EXT = 12     # keď druhý smer masívne stojí, nepredlžuj

# CUT (gap-out) – prázdno pri stop-čiare dlhšie + druhý smer čaká
GAP_OUT_SECS = 5
MIN_OTHER_LANE_HALT_FOR_CUT = 2
CUT_TO_REMAINING = 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--scale", type=float, default=5.0)
    ap.add_argument("--end", type=int, default=600)
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--delay", type=float, default=0.0)  # realtime delay pre GUI (napr. 0.1)
    ap.add_argument("--tripinfo", type=str, default=None)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    ctrl = FuzzyExtender()

    sumo_bin = "sumo-gui" if args.gui else "sumo"
    tripinfo = args.tripinfo or f"results/fuzzy_seed{args.seed}_tripinfo.xml"

    traci.start([
        sumo_bin,
        "-c", "net/mini.sumocfg",
        "--start",
        "--step-length", "1.0",
        "--scale", str(args.scale),
        "--seed", str(args.seed),
        "--end", str(args.end),
        "--tripinfo-output", tripinfo,
        "--no-step-log",
    ])

    last_phase = None
    green_start_time = None

    extended_this_green = False
    empty_streak = 0

    extend_count = 0
    cut_count = 0

    for _ in range(args.end):
        traci.simulationStep()
        t = traci.simulation.getTime()

        if args.gui and args.delay > 0:
            time.sleep(args.delay)

        phase = traci.trafficlight.getPhase(TLS_ID)  # 0=NS G,1=NS y,2=WE G,3=WE y
        next_switch = traci.trafficlight.getNextSwitch(TLS_ID)
        remaining = max(0.0, next_switch - t)

        in_green = phase in (0, 2)
        in_yellow = phase in (1, 3)

        if phase != last_phase:
            if in_green:
                green_start_time = t
                extended_this_green = False
                empty_streak = 0
            last_phase = phase

        if in_yellow or green_start_time is None:
            continue

        time_in_green = t - green_start_time
        if time_in_green < MIN_GREEN or time_in_green >= MAX_GREEN:
            continue

        # --- STOP-LINE detektory (lanearea) ---
        # Toto je "pri čiare": vhodné na gap-out CUT
        try:
            det_veh_ns = traci.lanearea.getLastStepVehicleNumber(DET_NS)
            det_veh_we = traci.lanearea.getLastStepVehicleNumber(DET_WE)
            det_halt_ns = traci.lanearea.getLastStepHaltingNumber(DET_NS)
            det_halt_we = traci.lanearea.getLastStepHaltingNumber(DET_WE)
        except traci.TraCIException as e:
            traci.close()
            raise RuntimeError(
                f"Neviem čítať lanearea detektory {DET_NS}/{DET_WE}. "
                f"Skontroluj mini_additional.add.xml a ID detektorov. Detail: {e}"
            )

        # --- CELÝ pruh (lane) ---
        # Toto je "tlak" na priblížení: vhodné na EXTEND rozhodovanie
        lane_veh_ns = traci.lane.getLastStepVehicleNumber(LANE_NS)
        lane_veh_we = traci.lane.getLastStepVehicleNumber(LANE_WE)
        lane_halt_ns = traci.lane.getLastStepHaltingNumber(LANE_NS)
        lane_halt_we = traci.lane.getLastStepHaltingNumber(LANE_WE)

        # served/other podľa fázy
        if phase == 0:  # NS green
            served = "NS"
            det_veh_s, det_veh_o = det_veh_ns, det_veh_we
            lane_veh_s, lane_veh_o = lane_veh_ns, lane_veh_we
            lane_halt_s, lane_halt_o = lane_halt_ns, lane_halt_we
        elif phase == 2:  # WE green
            served = "WE"
            det_veh_s, det_veh_o = det_veh_we, det_veh_ns
            lane_veh_s, lane_veh_o = lane_veh_we, lane_veh_ns
            lane_halt_s, lane_halt_o = lane_halt_we, lane_halt_ns
        else:
            continue

        # ---------------- CUT (gap-out) ----------------
        # "prázdno pri čiare" = detektor nemá žiadne auto
        if det_veh_s == 0:
            empty_streak += 1
        else:
            empty_streak = 0

        if (
            empty_streak >= GAP_OUT_SECS
            and lane_halt_o >= MIN_OTHER_LANE_HALT_FOR_CUT
            and remaining > CUT_TO_REMAINING
        ):
            traci.trafficlight.setPhaseDuration(TLS_ID, CUT_TO_REMAINING)
            cut_count += 1
            print(
                f"CUT   t={t:.0f}s phase={phase} served={served} "
                f"detVehS={det_veh_s} laneHaltO={lane_halt_o} -> remain={CUT_TO_REMAINING}"
            )
            continue

        # ---------------- EXTEND (raz za green) ----------------
        if extended_this_green:
            continue

        # rozhoduj len v okne pred switchom
        if remaining > DECIDE_WHEN_REMAINING_LE:
            continue

        if args.debug:
            print(
                f"DECIDE t={t:.0f}s phase={phase} served={served} remaining={remaining:.1f} "
                f"laneVehS={lane_veh_s} laneVehO={lane_veh_o} laneHaltO={lane_halt_o} detVehS={det_veh_s}"
            )

        # guardy – ak na served pruhu nie je tlak, nepredlžuj
        if lane_veh_s < MIN_SERVED_LANE_VEH_FOR_EXT:
            if args.debug:
                print(f"  SKIP: lane_veh_s({lane_veh_s}) < MIN_SERVED_LANE_VEH_FOR_EXT({MIN_SERVED_LANE_VEH_FOR_EXT})")
            continue

        # ak druhý smer už výrazne stojí, nepredlžuj
        if lane_halt_o > MAX_OTHER_LANE_HALT_FOR_EXT:
            if args.debug:
                print(f"  SKIP: lane_halt_o({lane_halt_o}) > MAX_OTHER_LANE_HALT_FOR_EXT({MAX_OTHER_LANE_HALT_FOR_EXT})")
            continue

        # fuzzy rozhodnutie (použi lane_veh_*)
        ext_raw = ctrl.decide(q_served=int(lane_veh_s), q_other=int(lane_veh_o))
        try:
            ext = int(round(ext_raw))
        except Exception:
            ext = 0

        ext = max(0, min(MAX_EXT, ext))

        if ext > 0 and (time_in_green + ext) <= MAX_GREEN:
            traci.trafficlight.setPhaseDuration(TLS_ID, remaining + ext)
            extended_this_green = True
            extend_count += 1
            print(
                f"EXTEND t={t:.0f}s phase={phase} served={served} +{ext}s "
                f"laneVehS={lane_veh_s} laneVehO={lane_veh_o} laneHaltO={lane_halt_o}"
            )
        else:
            if args.debug:
                print(f"  SKIP: ext={ext} or (time_in_green+ext)>{MAX_GREEN}")

    traci.close()
    print(f"Fuzzy run OK. extend_count={extend_count}, cut_count={cut_count}, tripinfo={tripinfo}")


if __name__ == "__main__":
    main()
