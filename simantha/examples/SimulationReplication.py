"""
This example compares the production of two systems, one under a corrective maintenance
policy and the other under a condition-based maintenance policy. The simulation
replication functionality is used to estimate the average production of both systems. 
"""

import random

from simantha import Source, Machine, Buffer, Sink, Maintainer, System, utils

def main():
    # Parameters for both systems
    degradation_matrix = [
        [0.9, 0.1, 0.,  0.,  0. ],
        [0.,  0.9, 0.1, 0.,  0. ],
        [0.,  0.,  0.9, 0.1, 0. ],
        [0.,  0.,  0.,  0.9, 0.1],
        [0.,  0.,  0.,  0.,  1. ]
    ]
    pm_distribution = {'geometric': 0.25} # Average PM duration: 4 minutes
    cm_distribution = {'geometric': 0.10} # Average CM duration: 10 minutes

    # Define the corrective maintenance system
    source = Source()
    M1 = Machine(
        name='M1', 
        cycle_time=1,
        degradation_matrix=degradation_matrix,
        cm_distribution=cm_distribution
    )
    B1 = Buffer(capacity=10)
    M2 = Machine(
        name='M2', 
        cycle_time=1,
        degradation_matrix=degradation_matrix,
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

    corrective_maintenance_system = System(objects=objects, maintainer=maintainer)    

    # Define the condition-based maintenance system
    cbm_threshold = 3
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
        cycle_time=1,
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

    condition_based_maintenance_system = System(objects=objects, maintainer=maintainer)

    # Simulate both systems
    replications = 50
    random.seed(1)
    
    cm_results = corrective_maintenance_system.iterate_simulation(
        replications=replications, 
        warm_up_time=utils.DAY, 
        simulation_time=utils.WEEK,
        jobs=10, # Simulate in parallel using 10 cores
        verbose=False
    )
    cm_production = [r[0] for r in cm_results]
    cm_average = sum(cm_production) / replications

    cbm_results = condition_based_maintenance_system.iterate_simulation(
        replications=replications, 
        warm_up_time=utils.DAY, 
        simulation_time=utils.WEEK,
        jobs=10,
        verbose=False
    )
    cbm_production = [r[0] for r in cbm_results]
    cbm_average = sum(cbm_production) / replications

    print(f'Average corrective maintenance production:       {cm_average:.2f} units')
    print(f'Average condition-based maintenance production:  {cbm_average:.2f} units')

if __name__ == '__main__':
    main()
