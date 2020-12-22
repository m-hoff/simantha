import random

from simantha import Source, Machine, Buffer, Sink, Maintainer, System, utils

def main():
    degradation_matrix = [
        [0.9, 0.1, 0.,  0.,  0. ],
        [0.,  0.9, 0.1, 0.,  0. ],
        [0.,  0.,  0.9, 0.1, 0. ],
        [0.,  0.,  0.,  0.9, 0.1],
        [0.,  0.,  0.,  0.,  1. ]
    ]

    source = Source()
    M1 = Machine(
        name='M1',
        cycle_time=1,
        degradation_matrix=degradation_matrix,
        cm_distribution={'geometric': 0.1}
    )
    B1 = Buffer(capacity=5)
    M2 = Machine(
        name='M2',
        cycle_time=1,
        degradation_matrix=degradation_matrix,
        cm_distribution={'geometric': 0.1}
    )
    sink = Sink()

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[B1])
    B1.define_routing(upstream=[M1], downstream=[M2])
    M2.define_routing(upstream=[B1], downstream=[sink])
    sink.define_routing(upstream=[M2])

    maintainer = Maintainer(capacity=1)
    system = System([source, M1, B1, M2, sink], maintainer=maintainer)

    random.seed(1)
    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
