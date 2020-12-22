from simantha import Source, Machine, Sink, System

def main():
    source = Source()
    M1 = Machine(name='M1', cycle_time=1)
    sink = Sink()

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[sink])
    sink.define_routing(upstream=[M1])

    system = System(objects=[source, M1, sink])

    system.simulate(simulation_time=100)

if __name__ == '__main__':
    main()
    