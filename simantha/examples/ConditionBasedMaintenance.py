"""
Example of a condition-based maintenance policy. The CBM threshold determines the health
index level at which a machine requests maintenance. 
"""

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
    cbm_threshold = 3
    pm_distribution = {'geometric': 0.25}
    cm_distribution = {'geometric': 0.10}

    source = Source()
    M1 = Machine(
        name='M1', 
        cycle_time=1,
        degradation_matrix=degradation_matrix,
        cbm_threshold=cbm_threshold,
        pm_distribution=pm_distribution,
        cm_distribution=cm_distribution
    )
    B1 = Buffer(capacity=10)
    M2 = Machine(
        name='M2', 
        cycle_time=2,
        degradation_matrix=degradation_matrix,
        cbm_threshold=cbm_threshold,
        pm_distribution=pm_distribution,
        cm_distribution=cm_distribution
    )
    sink = Sink()

    objects = [source, M1, B1, M2, sink]

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[B1])
    B1.define_routing(upstream=[M1], downstream=[M2])
    M2.define_routing(upstream=[B1], downstream=[sink])
    sink.define_routing(upstream=[M2])

    maintainer = Maintainer(capacity=1)

    system = System(objects=objects, maintainer=maintainer)

    random.seed(1)
    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
