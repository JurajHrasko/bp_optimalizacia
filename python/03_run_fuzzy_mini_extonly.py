import traci
from fuzzy_controller import FuzzyExtender

TLS_ID = "C"

DET_NS = "detNS"
DET_WE = "detWE"

SIM_END = 600
SEED = 1
DEMAND_SCALE = 5.0

MIN_GREEN = 12
MAX_GREEN = 90

DECIDE_WHEN_REMAINING_LE = 5.0   # s detektormi môžeš rozhodovať skôr (5s je stabilnejšie)
MAX_EXT = 10
ONE_EXT_PER_GREEN = True

# gap-out: rozhoduj podľa stojacich v detektore (pri stop čiare)
GAP_OUT_SECS = 5
MIN_OTHER_HALT_FOR_CUT = 2
CUT_TO_REMAINING = 2.0

def main():
    ctrl = FuzzyExtender()

    traci.start([
        "sumo",
        "-c", "net/mini.sumocfg",
        "--start",
        "--step-length", "1.0",
        "--scale", str(DEMAND_SCALE),
        "--seed", str(SEED),
        "--end", str(SIM_END),
        "--tripinfo-output", f"results/fuzzy_seed{SEED}_tripinfo.xml",
        "--no-step-log",
    ])

    last_phase = None
    green_start_time = None
    extended_this_green = False
    empty_streak = 0

    extend_count = 0
    cut_count = 0

    for _ in range(SIM_END):
        traci.simulationStep()
        t = traci.simulation.getTime()

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

        if ONE_EXT_PER_GREEN and extended_this_green:
            continue

        # hodnoty z detektorov pri stop čiare
        veh_ns = traci.lanearea.getLastStepVehicleNumber(DET_NS)
        veh_we = traci.lanearea.getLastStepVehicleNumber(DET_WE)
        halt_ns = traci.lanearea.getLastStepHaltingNumber(DET_NS)
        halt_we = traci.lanearea.getLastStepHaltingNumber(DET_WE)

        if phase == 0:
            served = "NS"
            q_served = veh_ns
            q_other = veh_we
            h_served = halt_ns
            h_other = halt_we
        elif phase == 2:
            served = "WE"
            q_served = veh_we
            q_other = veh_ns
            h_served = halt_we
            h_other = halt_ns
        else:
            continue

        # GAP-OUT (CUT): served nemá stojacich pri stop čiare, ale other už čaká
        if h_served == 0:
            empty_streak += 1
        else:
            empty_streak = 0

        if empty_streak >= GAP_OUT_SECS and h_other >= MIN_OTHER_HALT_FOR_CUT and remaining > CUT_TO_REMAINING:
            traci.trafficlight.setPhaseDuration(TLS_ID, CUT_TO_REMAINING)
            cut_count += 1
            print(f"CUT t={t:.0f}s phase={phase} served={served} halt_served={h_served} halt_other={h_other}")
            continue

        # EXTEND: rozhoduj v okne pred koncom zelenej, ale podľa áut v detektore
        if remaining > DECIDE_WHEN_REMAINING_LE:
            continue

        if q_served <= 0:
            continue

        ext = min(MAX_EXT, ctrl.decide(q_served=q_served, q_other=q_other))

        if ext > 0 and (time_in_green + ext) <= MAX_GREEN:
            traci.trafficlight.setPhaseDuration(TLS_ID, remaining + ext)
            extended_this_green = True
            extend_count += 1
            print(f"EXTEND t={t:.0f}s phase={phase} served={served} +{ext}s qS={q_served} qO={q_other} haltS={h_served} haltO={h_other}")

    traci.close()
    print(f"Fuzzy run OK. extend_count={extend_count}, cut_count={cut_count}")

if __name__ == "__main__":
    main()
