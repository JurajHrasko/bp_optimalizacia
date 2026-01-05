import argparse
import csv
from pathlib import Path
import xml.etree.ElementTree as ET

def parse_tripinfo(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()

    durations = []
    timelosses = []
    waiting = []

    for ti in root.findall("tripinfo"):
        durations.append(float(ti.get("duration", "0")))
        timelosses.append(float(ti.get("timeLoss", "0")))
        waiting.append(float(ti.get("waitingTime", "0")))

    arrived = len(durations)
    if arrived == 0:
        return arrived, 0.0, 0.0, 0.0

    avg_duration = sum(durations) / arrived
    avg_timeloss = sum(timelosses) / arrived
    avg_waiting = sum(waiting) / arrived
    return arrived, avg_duration, avg_timeloss, avg_waiting

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run id (napr. baseline_s1_d5)")
    ap.add_argument("--tripinfo", required=True)
    ap.add_argument("--out", default="results/metrics.csv")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)

    trip_path = Path(args.tripinfo)
    arrived, avg_duration, avg_timeloss, avg_waiting = parse_tripinfo(trip_path)

    # Upsert podľa stĺpca 'run' (nech sa ti to neduplikuje)
    rows = []
    if out.exists():
        with out.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    rows = [r for r in rows if r.get("run") != args.run]

    rows.append({
        "run": args.run,
        "arrived": str(arrived),
        "avg_duration": f"{avg_duration:.6f}",
        "avg_timeLoss": f"{avg_timeloss:.6f}",
        "avg_waitingTime": f"{avg_waiting:.6f}",
    })

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["run", "arrived", "avg_duration", "avg_timeLoss", "avg_waitingTime"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Metrics OK: {args.run} arrived={arrived} avg_waiting={avg_waiting:.3f}")

if __name__ == "__main__":
    main()
