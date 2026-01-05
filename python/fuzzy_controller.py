import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


class FuzzyExtender:
    """
    Vstupy:
      q_served, q_other = počet vozidiel v detekčnej zóne pri stop-čiare (laneAreaDetector)

    Výstup:
      extend = kvantizované sekundy {0, 3, 6, 10}
    """
    def __init__(self):
        q = np.arange(0, 21, 1)    # 0..20 vozidiel v zóne
        ext = np.arange(0, 11, 1)  # 0..10 s

        self.q_served = ctrl.Antecedent(q, "q_served")
        self.q_other = ctrl.Antecedent(q, "q_other")
        self.extend = ctrl.Consequent(ext, "extend")

        self.q_served["low"] = fuzz.trapmf(q, [0, 0, 2, 5])
        self.q_served["med"] = fuzz.trimf(q, [3, 7, 11])
        self.q_served["high"] = fuzz.trapmf(q, [9, 12, 20, 20])

        self.q_other["low"] = fuzz.trapmf(q, [0, 0, 2, 6])
        self.q_other["med"] = fuzz.trimf(q, [4, 8, 12])
        self.q_other["high"] = fuzz.trapmf(q, [10, 13, 20, 20])

        self.extend["zero"] = fuzz.trimf(ext, [0, 0, 2])
        self.extend["low"] = fuzz.trimf(ext, [2, 3, 5])
        self.extend["med"] = fuzz.trimf(ext, [4, 6, 8])
        self.extend["high"] = fuzz.trimf(ext, [7, 10, 10])

        rules = [
            ctrl.Rule(self.q_served["low"], self.extend["zero"]),
            ctrl.Rule(self.q_other["high"], self.extend["zero"]),
            ctrl.Rule(self.q_served["high"] & self.q_other["low"], self.extend["high"]),
            ctrl.Rule(self.q_served["high"] & self.q_other["med"], self.extend["med"]),
            ctrl.Rule(self.q_served["med"] & self.q_other["low"], self.extend["med"]),
            ctrl.Rule(self.q_served["med"] & self.q_other["med"], self.extend["low"]),
        ]

        system = ctrl.ControlSystem(rules)
        self.sim = ctrl.ControlSystemSimulation(system)

    def decide(self, q_served: int, q_other: int) -> int:
        q_served = int(max(0, min(20, q_served)))
        q_other = int(max(0, min(20, q_other)))

        self.sim.input["q_served"] = q_served
        self.sim.input["q_other"] = q_other
        self.sim.compute()

        raw = float(self.sim.output["extend"])  # 0..10
        # Kvantizácia na skoky (ľahko obhájiteľné v BP)
        if raw < 2.5:
            return 0
        elif raw < 4.5:
            return 3
        elif raw < 8.0:
            return 6
        else:
            return 10
