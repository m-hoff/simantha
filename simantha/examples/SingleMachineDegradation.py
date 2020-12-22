"""
An example of Markovian degradation of a single machine. The degradation matrix
specifies the health index transition probabilities. Once the machine reaches the
maximum health index it requires a corrective maintenance action to be restored. 
"""

import random

from simantha import Source, Machine, Sink, System, utils

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
    sink = Sink()

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[sink])
    sink.define_routing(upstream=[M1])

    system = System([source, M1, sink])

    random.seed(1)
    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
