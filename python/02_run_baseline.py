import argparse
import subprocess
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--scale", type=float, default=5.0)
    ap.add_argument("--end", type=int, default=600)
    ap.add_argument("--tripinfo", type=str, default=None)
    args = ap.parse_args()

    Path("results").mkdir(exist_ok=True)

    tripinfo = args.tripinfo or f"results/baseline_seed{args.seed}_tripinfo.xml"

    cmd = [
        "sumo",
        "-c", "net/mini.sumocfg",
        "--start",
        "--step-length", "1.0",
        "--scale", str(args.scale),
        "--seed", str(args.seed),
        "--end", str(args.end),
        "--tripinfo-output", tripinfo,
        "--no-step-log",
    ]
    subprocess.check_call(cmd)
    print(f"Baseline run OK. tripinfo={tripinfo}")

if __name__ == "__main__":
    main()
