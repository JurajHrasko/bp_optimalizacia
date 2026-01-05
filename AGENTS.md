# AGENTS

## Bachelor thesis context
This repository supports a bachelor thesis focused on SUMO traffic simulation, TraCI-based control, and fuzzy/actuated control strategies for signalized intersections.

## Mini scenario facts
- `net/mini.sumocfg`
- TLS id `C`
- Key lanes: `N2C_0` and `W2C_0`

## Preference
Use stop-line laneAreaDetectors instead of whole-lane vehicle counts.

## Definition of Done
Scripts run end-to-end, produce `results/tripinfo*.xml`, and report `extend_count`/`cut_count`.
