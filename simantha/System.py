import copy
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


    def iterate_simulation(
        self, 
        replications, 
        warm_up_time=0, 
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
