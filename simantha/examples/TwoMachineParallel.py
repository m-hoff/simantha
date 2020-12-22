from simantha import Source, Machine, Sink, System, utils

def main():
    source = Source()
    M1 = Machine(name='M1', cycle_time=1)
    M2 = Machine(name='M2', cycle_time=1)
    sink = Sink()

    source.define_routing(downstream=[M1, M2])
    M1.define_routing(upstream=[source], downstream=[sink])
    M2.define_routing(upstream=[source], downstream=[sink])
    sink.define_routing(upstream=[M1, M2])

    system = System([source, M1, M2, sink])

    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
