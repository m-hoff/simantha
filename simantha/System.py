import copy
<<<<<<< HEAD
import time

from joblib import Parallel, delayed
import numpy as np
import pandas as pd
from scipy import stats
import simpy

from .Machine import *
from .Repairman import Repairman


class System:
    def __init__(
        self, 
        cycle_times,                 
        buffer_capacity=1,
        degradation_matrices=None,
        maintenance_policy=None, # CBM policy
        repairman=None,
        maintenance_capacity=1,
        scheduling_policy='FIFO',
        pm_distribution=None,
        cm_distribution=None,
        
        initial_health_states=None,
        initial_remaining_process=None,
        initial_buffer_level=None,
        
        allow_new_failures=True,
        initial_time=None,

        mcts_system=False
    ):
        self.n = len(cycle_times)
        self.cycle_times = cycle_times
        self.bottleneck = np.argmax(cycle_times)
        self.buffer_capacity = buffer_capacity
        
        self.degradation_matrices = degradation_matrices
        
        self.repairman = repairman
        self.maintenance_policy = maintenance_policy
        self.maintenance_capacity = maintenance_capacity
        self.scheduling_policy = scheduling_policy
        
        self.pm_distribution = pm_distribution
        self.cm_distribution = cm_distribution

        if initial_health_states:
            self.initial_health_states = initial_health_states
        else:
            self.initial_health_states = [0] * self.n

        if initial_remaining_process:
            self.initial_remaining_process = initial_remaining_process
        else:
            self.initial_remaining_process = [None] * self.n

        if initial_buffer_level:
            self.initial_buffer_level = initial_buffer_level
        else:
            self.initial_buffer_level = [0] * self.n
        
        self.allow_new_failures = allow_new_failures
        self.initial_time = initial_time

        self.initialize()

        self.debug = False
        self.mcts_system = mcts_system


    def initialize(self):
        # intialize simulation objects
        self.env = simpy.Environment()

        if self.initial_time:
            self.env.run(until=self.initial_time)
        
        self.buffers = []
        for i in range(self.n):
            self.buffers.append(
                simpy.Container(
                    self.env, 
                    capacity=self.buffer_capacity,
                    init=self.initial_buffer_level[i]
                )            
            )
            self.buffers[i].buffer_data = np.array([[0,0]])
        
        self.machines = []                
        for i, cycle_time in enumerate(self.cycle_times):
            if self.degradation_matrices:
                degradation_matrix = self.degradation_matrices[i]
            else:
                degradation_matrix = Machine.degradation_matrix
                
            if self.maintenance_policy:
                maintenance_threshold = self.maintenance_policy[i]
            else:
                maintenance_threshold = degradation_matrix.shape[0]
                
            if self.n == 1: # single-machine line
                self.machines.append(
                    Machine(
                        self.env, 
                        self, 
                        i, 
                        cycle_time,
                        degradation_matrix=degradation_matrix,
                        maintenance_threshold=maintenance_threshold,
                        initial_health=self.initial_health_states[i],
                        initial_remaining_process=self.initial_remaining_process[i],
                        allow_new_failures=self.allow_new_failures
                    )
                )
            elif i == 0: # first machine
                self.machines.append(
                    Machine(
                        self.env, 
                        self, 
                        i, 
                        cycle_time, 
                        out_buffer=self.buffers[i],
                        degradation_matrix=degradation_matrix,
                        maintenance_threshold=maintenance_threshold,
                        initial_health=self.initial_health_states[i],
                        allow_new_failures=self.allow_new_failures
                    )
                )
            elif 0 < i < self.n - 1:
                self.machines.append(
                    Machine(
                        self.env, 
                        self, 
                        i, 
                        cycle_time, 
                        in_buffer=self.buffers[i-1], out_buffer=self.buffers[i],
                        degradation_matrix=degradation_matrix,
                        maintenance_threshold=maintenance_threshold,
                        initial_health=self.initial_health_states[i],
                        initial_remaining_process=self.initial_remaining_process[i],
                        allow_new_failures=self.allow_new_failures
                    )
                )
            else: # i == len(cycle_times) - 1, last machine
                self.machines.append(
                    Machine(
                        self.env, 
                        self, 
                        i, 
                        cycle_time, 
                        in_buffer=self.buffers[i-1],
                        degradation_matrix=degradation_matrix,
                        maintenance_threshold=maintenance_threshold,
                        initial_health=self.initial_health_states[i],
                        initial_remaining_process=self.initial_remaining_process[i],
                        allow_new_failures=self.allow_new_failures
                    )
                )
        
        if not self.repairman:
            # default FIFO scheduler
            self.repairman = Repairman(
                self.env, 
                system=self, 
                capacity=self.maintenance_capacity,
                scheduling_policy='FIFO'
            )
        else:
            # currently only works for MctsRepairman.MctsRepairman object
            self.repairman.__init__(
                env=self.env, 
                system=self, 
                capacity=self.maintenance_capacity, 
                scheduling_policy=self.scheduling_policy,
                #time_limit=self.repairman.time_limit,
                #iteration_limit=self.repairman.iteration_limit
            )

            # MCTS limits are hardcoded here
            if self.scheduling_policy == 'MCTS':
                self.repairman.limit = {'timeLimit': 1000}


        self.queue_data = None
    

    def simulate(
        self, 
        warm_up_time=0, 
        simulation_time=0, 
        verbose=True, 
        debug=False
    ):
        self.initialize() # reinitialize system
        
        # main simulation function 
        self.warm_up_time = warm_up_time
        self.simulation_time = simulation_time
        
        self.debug = debug
        
        # simulate the machines for the specified time
        self.total_time = warm_up_time + simulation_time
        
        start_time = time.time()
        self.env.run(until=self.total_time)
        stop_time = time.time()        
        
        if verbose:
            print(f'Finished in {stop_time-start_time:.4f}s')
            print(f'Units produced: {self.machines[-1].parts_made}')

        # clean up data

        # queue data
        self.queue_data = pd.DataFrame(
            self.repairman.queue_data,
            columns=['time', 'queue level']
        ).set_index('time')

        self.queue_data = self.queue_data[
            ~self.queue_data.index.duplicated(keep='last')
        ]

        self.queue_data = self.queue_data.reindex(
            index=range(self.warm_up_time+self.simulation_time+1)
        )

        self.queue_data.loc[0, 'queue level'] = 0
        self.queue_data.ffill(inplace=True)

        # health data


        # production data



    def continue_simulation(self, simulation_time, debug=False):
        # simulate from current state without reinitializing
        self.debug = debug

        self.repairman.schedule_maintenance()

        self.env.run(until=self.env.now+simulation_time)

=======
import multiprocessing
import random
import time
import warnings

from .simulation import Environment
from .Source import Source
from .Sink import Sink
from .Machine import Machine
from .Buffer import Buffer
from .Maintainer import Maintainer

class System:
    def __init__(
        self,
        objects=[],
        maintainer=Maintainer()
    ):
        self.objects = objects
        self.sources = []
        self.machines = []
        self.buffers = []
        self.sinks = []
        for obj in objects:
            if type(obj) == Source:
                self.sources.append(obj)
            #elif type(obj) == Machine:
            elif isinstance(obj, Machine):
                self.machines.append(obj)
            elif type(obj) == Buffer:
                self.buffers.append(obj)
            elif type(obj) == Sink:
                self.sinks.append(obj)
        self.maintainer = maintainer

        # put machines at the front as they should be initialized first
        self.objects.sort(key=lambda obj: not isinstance(obj, Machine))
    
    def initialize(self):
        for machine in self.machines:
            machine.remaining_process_time = machine.initial_remaining_process
            machine.parts_made = 0
            machine.health = machine.initial_health

            if len(machine.upstream) > 1 or len(machine.downstream) > 1:
                warnings.warn(
                    'System configuration includes machines with more than one asset '
                    + 'upstream or downstream, which may result in unexepcted behavior. '
                    + 'It is recommended that the system be rearranged such that each '
                    + 'machine gives and takes from only one buffer.'
                )

        for buffer in self.buffers:
            buffer.level = buffer.initial_level
        
        for sink in self.sinks:
            sink.level = sink.initial_level

        self.maintainer.utilization = 0

    def simulate(
        self,
        warm_up_time=0,
        simulation_time=0,
        verbose=True,
        trace=False,
        collect_data=True
    ):
        start = time.time()
        for machine in self.machines:
            machine.maintainer = self.maintainer

        self.env = Environment(trace=trace, collect_data=collect_data)
        for obj in self.objects:
            # should initialize machines first
            obj.env = self.env
            obj.initialize()

        self.maintainer.env = self.env
        self.maintainer.system = self
        self.maintainer.utilization = 0

        self.warm_up_time = warm_up_time
        self.simulation_time = simulation_time

        self.env.run(warm_up_time, simulation_time)

        # clean up data here
        for machine in self.machines:
            if machine.under_repair or machine.failed:
                machine.downtime += (self.env.now - machine.downtime_start)

        stop = time.time()
        if verbose:
            print(f'Simulation finished in {stop-start:.2f}s')
            print(f'Parts produced: {sum([sink.level for sink in self.sinks])}')
>>>>>>> dev

    def iterate_simulation(
        self, 
        replications, 
        warm_up_time=0, 
<<<<<<< HEAD
        simulation_time=100, 
        objective='production', 
        verbose=True
    ):
        results = []
        
        start_time = time.time()

        for _ in range(replications):                        
            self.simulate(warm_up_time, simulation_time, verbose=False)
            if objective == 'production':
                results.append(self.machines[-1].parts_made)
        
        stop_time = time.time()
        
        if verbose:
            print(f'Finished in {stop_time-start_time:.4f}s,', 
                  f'{(stop_time-start_time)/replications:.4f}s/replication')
            print(f'Average objective value: {np.mean(results):.2f} units')
        
        return results
    

    def get_queue(self):
        # returns a list of machines in the current maintenance queue
        queue = [machine for machine in self.machines if machine.in_queue]
        return queue


    def tidy_data(self):
        # cleans up data after simulation
        return


# def get_system_copy(system):
#     # returns a deep copy of a System instance
#     system_copy = System([1])

#     env_copy = copy.deepcopy(system.env)

#     system_copy.__dict__ = system.__dict__
#     system_copy.env = env_copy

#     for i, buffer in enumerate(system_copy.buffers):
#         system_copy.buffers[i] = simpy.Container(
#             env_copy, buffer.capacity, buffer.level
#         )

#     for j, machine in enumerate(system_copy.machines):
#         machine.env = env_copy


def main():
    np.random.seed(1)
    system = System(
        cycle_times=[3, 5, 4],
        buffer_capacity=5,
        pm_distribution=stats.randint(10,20),
        cm_distribution=stats.randint(20,40)
    )

    print('Simulating system...')
    system.simulate(warm_up_time=100, simulation_time=1000)

    print('\nIterating simulation...')
    _ = system.iterate_simulation(10, warm_up_time=10, simulation_time=1000)
    print()

if __name__ == '__main__':
    main()
=======
        simulation_time=0,
        store_system_state=False,
        verbose=True,
        jobs=1,
        seedseed=0
    ):
        """Replicate multiple simulation runs for a specified system. Statistics for
        each run will gathered after the "warm_up_time" has elapsed. Currently the
        following statistics are gathered:
        - Machine
            - Production (units)
            - Availability (proportion of time not failed or under maintenance)
        - Sink
            - Level (units): completed parts that have exited the system

        A nested dictionary is returned with "replications" samples of each statistic.
        """
        start = time.time()      
        with multiprocessing.Pool(jobs) as p:
            args = [
                (seed, warm_up_time, simulation_time, store_system_state)
                for seed in range(seedseed, seedseed+replications)
            ]
            samples = p.starmap(self.simulate_in_parallel, args)
        stop = time.time()

        if verbose:
            print(f'Finished {replications} replications in {stop-start:.2f}s')
        
        return samples

    def simulate_in_parallel(
        self, 
        seed, 
        warm_up_time, 
        simulation_time, 
        store_system_state=False
    ):
        random.seed()
        
        self.simulate(
            warm_up_time, 
            simulation_time, 
            verbose=False, 
            collect_data=store_system_state
        )

        availability = [
            (1 - machine.downtime/(warm_up_time+simulation_time)) 
            for machine in self.machines
        ]

        machine_production = [machine.parts_made for machine in self.machines]

        system_production = sum([sink.level for sink in self.sinks])

        if store_system_state:
            system_state = copy.deepcopy(self)
        else:
            system_state = None

        return (
            system_production, 
            machine_production, 
            availability, 
            system_state
        )
>>>>>>> dev
