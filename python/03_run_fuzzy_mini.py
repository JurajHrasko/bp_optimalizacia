import time
import traci
from fuzzy_controller import FuzzyExtender

TLS_ID = "C"
LANE_NS = "N2C_0"
LANE_WE = "W2C_0"

# Parametre riadenia
MIN_GREEN = 8
MAX_GREEN = 45

# Rozhodujeme tesne pred koncom plánovanej zelenej
DECIDE_WHEN_REMAINING_LE = 2.0

# Toto je kľúč: na začiatku zelenej nastavíme krátku "základnú" dĺžku,
# aby sme vôbec mali čo predlžovať.
BASE_GREEN = int(MIN_GREEN + DECIDE_WHEN_REMAINING_LE)  # typicky 10s

SIM_STEPS = 400
REALTIME_DELAY_S = 0.1

# Ak served nemá aspoň toľko stojacich áut, nepredlžuj (zmysluplné)
MIN_SERVED_QUEUE = 1

# (voliteľné) Zvyš dopravu bez editovania .rou.xml
DEMAND_SCALE = 3.0

def quantize_extension(ext_0_10: int) -> int:
    """0..10 -> 0/5/10"""
    if ext_0_10 < 3:
        return 0
    elif ext_0_10 < 8:
        return 5
    else:
        return 10

def main():
    ctrl = FuzzyExtender()

    SEED = 5
    SIM_STEPS = 600

    traci.start([
        "sumo-gui",
        "-c", "net/mini.sumocfg",
        "--start",
        "--step-length", "1.0",
        "--scale", str(DEMAND_SCALE),
        "--seed", str(SEED),
        "--tripinfo-output", f"results/fuzzy_seed{SEED}_tripinfo.xml",
        "--no-step-log",
    ])

    last_phase = None
    green_start_time = None
    extended_this_green = False
    forced_base_this_green = False

    for _ in range(SIM_STEPS):
        traci.simulationStep()
        t = traci.simulation.getTime()

        if REALTIME_DELAY_S > 0:
            time.sleep(REALTIME_DELAY_S)

        # 0=NS green, 1=NS yellow, 2=WE green, 3=WE yellow
        phase = traci.trafficlight.getPhase(TLS_ID)
        next_switch = traci.trafficlight.getNextSwitch(TLS_ID)
        remaining = max(0.0, next_switch - t)

        in_green = phase in (0, 2)
        in_yellow = phase in (1, 3)

        # Detekcia začiatku novej zelenej
        if phase != last_phase:
            if in_green:
                green_start_time = t
                extended_this_green = False
                forced_base_this_green = False
            last_phase = phase

        # počas žltej nič nerob
        if in_yellow or green_start_time is None:
            continue

        time_in_green = t - green_start_time

        q_ns = traci.lane.getLastStepHaltingNumber(LANE_NS)
        q_we = traci.lane.getLastStepHaltingNumber(LANE_WE)

        # každých 10s základný log
        if int(t) % 10 == 0:
            print(
                f"t={t:>4.0f}s phase={phase} qNS={q_ns} qWE={q_we} "
                f"remaining={remaining:.1f} time_in_green={time_in_green:.1f}"
            )

        # 1) Na začiatku zelenej skráť jej plán na BASE_GREEN, aby mala fuzzy šancu predĺžiť
        if in_green and (not forced_base_this_green) and time_in_green <= 1.0:
            # nastav zostávajúci čas fázy na BASE_GREEN
            traci.trafficlight.setPhaseDuration(TLS_ID, float(BASE_GREEN))
            forced_base_this_green = True
            # po zmenšení dĺžky môže byť "remaining" z toolu o krok pozadu, nevadí

        # 2) Rozhodovanie tesne pred koncom plánovanej zelenej (len raz na fázu)
        if (not extended_this_green) and remaining <= DECIDE_WHEN_REMAINING_LE and MIN_GREEN <= time_in_green < MAX_GREEN:

            if phase == 0:
                served = "NS"
                q_served = q_ns
                q_other = q_we
            elif phase == 2:
                served = "WE"
                q_served = q_we
                q_other = q_ns
            else:
                continue

            # Debug rozhodovania
            print(f"DECIDE t={t:.0f}s served={served} q_served={q_served} q_other={q_other} remaining={remaining:.1f}")

            if q_served < MIN_SERVED_QUEUE:
                print(f"  SKIP: q_served({q_served}) < MIN_SERVED_QUEUE({MIN_SERVED_QUEUE})")
                continue

            ext_raw = ctrl.decide(q_served=q_served, q_other=q_other)  # 0..10
            ext = quantize_extension(ext_raw)                          # 0/5/10
            print(f"  FUZZY: raw={ext_raw} -> quantized={ext}")

            if ext <= 0:
                print("  SKIP: ext == 0")
                continue

            if (time_in_green + ext) > MAX_GREEN:
                print(f"  SKIP: would exceed MAX_GREEN ({time_in_green:.1f} + {ext} > {MAX_GREEN})")
                continue

            traci.trafficlight.setPhaseDuration(TLS_ID, remaining + ext)
            extended_this_green = True
            print(f"  EXTEND APPLIED: +{ext}s")

    traci.close()
    print("Fuzzy run OK")

if __name__ == "__main__":
    main()
