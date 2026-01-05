import traci

def main():
    traci.start(["sumo-gui", "-c", "net/mini.sumocfg", "--start", "--step-length", "1.0"])

    traci.simulationStep()  # init

    print("TLS IDs:", traci.trafficlight.getIDList())
    print("Lane IDs:", traci.lane.getIDList())

    traci.close()

if __name__ == "__main__":
    main()
