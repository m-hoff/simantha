from simantha import Source, Machine, Buffer, Sink, System, utils

def main():
    source = Source()

    M1 = Machine('M1', cycle_time=2)
    M2 = Machine('M2', cycle_time=2)
    station1 = [M1, M2]

    B1 = Buffer(capacity=5)

    M3 = Machine('M3', cycle_time=3)
    M4 = Machine('M4', cycle_time=3)
    M5 = Machine('M5', cycle_time=3)
    station2 = [M3, M4, M5]

    B2 = Buffer(capacity=5)

    M6 = Machine('M6', cycle_time=2)
    M7 = Machine('M7', cycle_time=2)
    station3 = [M6, M7]

    sink = Sink()

    source.define_routing(downstream=station1)
    for machine in station1:
        machine.define_routing(upstream=[source], downstream=[B1])
    B1.define_routing(upstream=station1, downstream=station2)
    for machine in station2:
        machine.define_routing(upstream=[B1], downstream=[B2])
    B2.define_routing(upstream=station2, downstream=station3)
    for machine in station3:
        machine.define_routing(upstream=[B2], downstream=[sink])
    sink.define_routing(upstream=station3)

    objects = [source] + station1 + [B1] + station2 + [B2] + station3 + [sink]
    system = System(objects)

    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
