import subprocess
import sys
from pathlib import Path

SIM_END = 600
SCALES = [1.0, 5.0]
SEEDS = [1, 2, 3, 4, 5]

def run(cmd):
    print("\n>>", " ".join(map(str, cmd)))
    subprocess.check_call(cmd)

def main():
    Path("results").mkdir(exist_ok=True)
    Path("net/results").mkdir(parents=True, exist_ok=True)

    for scale in SCALES:
        for seed in SEEDS:
            base_trip = f"results/baseline_s{seed}_d{int(scale)}_tripinfo.xml"
            fuzzy_trip = f"results/fuzzy_s{seed}_d{int(scale)}_tripinfo.xml"

            run([sys.executable, "python/02_run_baseline.py",
                 "--seed", str(seed), "--scale", str(scale), "--end", str(SIM_END),
                 "--tripinfo", base_trip])

            run([sys.executable, "python/03_run_fuzzy_mini_actuated.py",
                 "--seed", str(seed), "--scale", str(scale), "--end", str(SIM_END),
                 "--tripinfo", fuzzy_trip])

            run([sys.executable, "python/05_metrics_tripinfo.py",
                 "--run", f"baseline_s{seed}_d{int(scale)}", "--tripinfo", base_trip])

            run([sys.executable, "python/05_metrics_tripinfo.py",
                 "--run", f"fuzzy_s{seed}_d{int(scale)}", "--tripinfo", fuzzy_trip])

    print("\nDONE. Pozri results/metrics.csv")

if __name__ == "__main__":
    main()
