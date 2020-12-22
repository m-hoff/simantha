from simantha import Source, Machine, Buffer, Sink, System, utils

def main():
    source = Source()
    M1 = Machine(name='M1', cycle_time=1)
    B1 = Buffer(capacity=5)
    M2 = Machine(name='M2', cycle_time=1)
    sink = Sink()

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[B1])
    B1.define_routing(upstream=[M1], downstream=[M2])
    M2.define_routing(upstream=[B1], downstream=[sink])
    sink.define_routing(upstream=[M2])

    system = System([source, M1, B1, M2, sink])

    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
