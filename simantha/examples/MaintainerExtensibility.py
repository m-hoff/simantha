"""
An example of the extensibility of the Maintainer class. A "least processing time first"
(LPT) policy is implemented.
"""

import random

from simantha import Source, Machine, Buffer, Sink, Maintainer, System, utils

class LptMaintainer(Maintainer):
    """Chooses the maintenance action with the longest expected duration first."""
    def choose_maintenance_action(self, queue):
        def expected_repair_time(machine):
            if machine.failed: # Machine requires corrective maintenance
                return machine.cm_distribution.mean
            else: # Machine requires preventive maintenance
                return machine.pm_distribution.mean

        return max(queue, key=expected_repair_time)

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
    B1 = Buffer(capacity=10)
    M2 = Machine(
        name='M2', 
        cycle_time=1,
        degradation_matrix=degradation_matrix,
        cm_distribution={'geometric': 0.075}
    )
    B2 = Buffer(capacity=10)
    M3 = Machine(
        name='M3', 
        cycle_time=1,
        degradation_matrix=degradation_matrix,
        cm_distribution={'geometric': 0.05}
    )
    sink = Sink()

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[B1])
    B1.define_routing(upstream=[M1], downstream=[M2])
    M2.define_routing(upstream=[B1], downstream=[B2])
    B2.define_routing(upstream=[M2], downstream=[M3])
    M3.define_routing(upstream=[B2], downstream=[sink])
    sink.define_routing(upstream=[M3])

    objects = [source, M1, B1, M2, B2, M3, sink]
    maintainer = LptMaintainer()

    system = System(objects, maintainer)

    random.seed(1)
    system.simulate(simulation_time=utils.WEEK)

if __name__ == '__main__':
    main()
