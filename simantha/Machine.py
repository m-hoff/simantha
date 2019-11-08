import time

import numpy as np
from scipy import stats
import simpy


class Machine:    
    degradation_matrix = np.array([[0.9, 0.1, 0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.],
                                   [0.,  0.9, 0.1, 0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.],
                                   [0.,  0.,  0.9, 0.1, 0.,  0.,  0.,  0.,  0.,  0.,  0.],
                                   [0.,  0.,  0.,  0.9, 0.1, 0.,  0.,  0.,  0.,  0.,  0.],
                                   [0.,  0.,  0.,  0.,  0.9, 0.1, 0.,  0.,  0.,  0.,  0.],
                                   [0.,  0.,  0.,  0.,  0.,  0.9, 0.1, 0.,  0.,  0.,  0.],
                                   [0.,  0.,  0.,  0.,  0.,  0.,  0.9, 0.1, 0.,  0.,  0.],
                                   [0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.9, 0.1, 0.,  0.],
                                   [0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.9, 0.1, 0.],
                                   [0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.9, 0.1],
                                   [0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  1.]])

    def __init__(
        self, 
        env, 
        system, 
        index, 
        cycle_time, 
        in_buffer=None, 
        out_buffer=None, 
        degradation_matrix=degradation_matrix, 
        maintenance_threshold=999,
        repairman=None, 
        initial_health=0, 
        initial_remaining_process=None,
        allow_new_failures=True
    ):

        self.env = env
        self.system = system
        
        self.index = index
        
        self.cycle_time = cycle_time
        self.in_buffer = in_buffer
        self.out_buffer = out_buffer
        self.degradation_matrix = degradation_matrix
        self.failed_state = degradation_matrix.shape[0] - 1
        self.allow_new_failures = allow_new_failures

        # maintenance parameters
        self.maintenance_threshold = min(
            [self.failed_state, maintenance_threshold]
        )
        
        # production state
        self.parts_made = 0
        if initial_remaining_process:
            self.remaining_processing_time = initial_remaining_process
            self.has_part = True
        else:
            self.remaining_processing_time = cycle_time
            self.has_part = False
        
        # maintenance state
        self.health = initial_health
        self.health_data = np.array([[0, 0]])
        self.maintenance_state = 'healthy' # healthy, unhealthy, failed
        
        if self.health >= self.maintenance_threshold:
            self.in_queue = True
            self.allow_new_failures = True
        else:
            self.in_queue = False
            self.allow_new_failures = allow_new_failures

        self.failed = False
        self.under_repair = False
        self.repair_type = None
        self.time_entered_queue = np.inf
        self.repairman = repairman
        self.repair_event = self.env.event()
        
        # machine data
        self.production_data = []
        self.maintenance_data = []
        
        self.production_process = self.env.process(self.production())
        self.degradation_process = self.env.process(self.degradation())


    def production(self):
        # if failed, should sleep until woken up
        while True:
            try:
                if self.in_buffer and (not self.has_part):
                    yield self.in_buffer.get(1)
                    self.update_in_buffer_data(self.env.now)
                self.has_part = True

                # TEMP DEBUG
                #if (self.index == self.system.n - 1) and (not self.system.mcts_system):
                #    print(f'M{self.index} got part at t={self.env.now}')
                
                while self.remaining_processing_time:
                    yield self.env.timeout(1)
                    self.remaining_processing_time -= 1
                self.remaining_processing_time = self.cycle_time
                
                if self.out_buffer:
                    yield self.out_buffer.put(1)
                    self.update_out_buffer_data(self.env.now)
                self.has_part = False

                # TEMP DEBUG
                #if (self.index == self.system.n - 1) and (not self.system.mcts_system):
                #    print(f'M{self.index} put part at t={self.env.now}')
                
                if (
                    (self.env.now >= self.system.warm_up_time) 
                    or (self.system.mcts_system)
                ):
                    self.parts_made += 1
                    self.production_data.append(
                        [self.env.now-self.system.warm_up_time, self.parts_made]
                    )

                # TEMP DEBUG
                #if (self.index == self.system.n - 1) and (not self.system.mcts_system):
                #    if self.system.mcts_system:
                #        print('MCTS: ', end='')
                #    print(f'M{self.index} finished part at t={self.env.now}, total production: {self.parts_made}')

            except simpy.Interrupt:
                if self.system.debug:
                    if self.system.mcts_system:
                        print('MCTS: ', end='')
                    print(f'M{self.index} stopped production at t={self.env.now}')

                yield self.repair_event # wait for repair to finish

                if self.system.debug:
                    if self.system.mcts_system:
                        print('MCTS: ', end='')
                    print(f'M{self.index} repaired at t={self.env.now}')
                
                self.repair_event = self.env.event()
                self.degradation_process = self.env.process(self.degradation())
                
                self.system.repairman.schedule_maintenance()       


    def degradation(self):
        try:
            if self.maintenance_threshold < self.failed_state:
                # time until enter maintenance queue
                ttq = self.get_time_to_queue()
                yield self.env.timeout(ttq)

                self.repair_type = 'preventive'
                self.time_entered_queue = self.env.now
                self.in_queue = True

                if self.system.debug:
                    if self.system.mcts_system:
                        print('MCTS: ', end='')
                    print(f'M{self.index} entered queue at t={self.env.now} with health {self.get_health(self.env.now)}')

                self.system.repairman.schedule_maintenance()

            # time until complete failure
            ttf = self.get_time_to_failure()
            yield self.env.timeout(ttf)
            self.repair_type = 'corrective'
            self.failed = True
            if not self.in_queue:
                self.in_queue = True
                self.time_entered_queue = self.env.now
                self.system.repairman.schedule_maintenance()

            if self.system.debug:
                if self.system.mcts_system:
                    print('MCTS: ', end='')
                print(f'M{self.index} failed at t={self.env.now}')

            self.production_process.interrupt()

        except simpy.Interrupt:
            # degradation interrupted if maintenance is scheduled before failure
            yield self.repair_event

            
    def repair(self):
        self.in_queue = False
        self.under_repair = True

        self.system.repairman.update_queue_data()

        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'M{self.index} starting repair at t={self.env.now}')

        #self.maintenance_request = self.system.repairman.request(priority=1)
        if self.repair_type == 'preventive':
            self.degradation_process.interrupt()
            self.production_process.interrupt()

            # clear health data beyond this point
        self.health_data = self.health_data[self.health_data[:,0] < self.env.now]

        ttr = self.get_time_to_repair()
        self.maintenance_data.append([self.env.now-self.system.warm_up_time,
                                      self.repair_type, ttr])
        yield self.env.timeout(ttr)

        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'M{self.index} repair completed at t={self.env.now}')

        self.health = 0 # machine completely restored
        self.update_health_data(at=self.env.now)

        self.failed = False
        self.under_repair = False
        self.remaining_processing_time = self.cycle_time

        if not self.system.allow_new_failures:
            if self.system.debug:
                if self.system.mcts_system:
                    print('MCTS: ', end='')
                print(f'M{self.index} disallowing additional failures at t={self.env.now}')

            self.allow_new_failures = False
            self.in_queue = False

        self.repair_event.succeed()
        self.system.repairman.utilization -= 1 # release repairman

        #self.system.repairman.update_queue_data()

    def get_time_to_repair(self):
        if self.get_health(self.env.now) < self.failed_state:
            self.repair_type = 'preventive'
        else:
            self.repair_type = 'corrective'

        if self.repair_type == 'preventive':
            ttr = self.system.pm_distribution.rvs()
        elif self.repair_type == 'corrective':
            ttr = self.system.cm_distribution.rvs()
        else:
            raise ValueError('Invalid repair type')

        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'M{self.index} {self.repair_type} TTR:', ttr)

        return ttr


    def get_time_to_queue(self):
        # time to enter the maintenance queue
        #current_health = self.health
        if (
            (1 in np.diagonal(self.degradation_matrix)[:-1]) 
            or (not self.allow_new_failures)
        ):
            #if self.system.debug:
            #    print(f'M{self.index} TTQ is inf')
            ttq = np.inf
        else:
            ttq = 0
            while self.health < self.maintenance_threshold: # TODO: verify '<' here
                previous_health = self.health
                all_states = np.arange(self.failed_state + 1)
                self.health = np.random.choice(
                    all_states, p=self.degradation_matrix[self.health]
                )
                if self.health != previous_health:
                    self.update_health_data(at=self.env.now+ttq)
                ttq += 1

        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'M{self.index} TTQ: {ttq} at t={self.env.now}')

        return ttq
    
    
    def get_time_to_failure(self):
        if (
            (1 in np.diagonal(self.degradation_matrix)[:-1])
            or ((not self.allow_new_failures) and (not self.in_queue))
        ):
            #if self.system.debug:
            #    print(f'M{self.index} TTF is inf')
            ttf = np.inf
        else:
            ttf = 0
            while self.health != self.failed_state:
                previous_health = self.health
                all_states = np.arange(self.failed_state + 1)
                self.health = np.random.choice(
                    all_states, p=self.degradation_matrix[self.health]
                )
                if self.health != previous_health:
                    self.update_health_data(at=self.env.now+ttf)
                ttf +=1

        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'M{self.index} TTF: {ttf} at t={self.env.now}')

        return ttf

    
    def update_health_data(self, at=None):
        self.health_data = np.append(
            self.health_data, [[at, self.health]], axis=0
        )


    def update_in_buffer_data(self, at=None):
        if at in self.in_buffer.buffer_data[:,0]:
            i = np.where(self.in_buffer.buffer_data[:,0] == at)
            self.in_buffer.buffer_data[i] = [at, self.in_buffer.level]
        else:
            self.in_buffer.buffer_data = np.append(
                self.in_buffer.buffer_data, 
                [[at, self.in_buffer.level]], 
                axis=0
            )


    def update_out_buffer_data(self, at=None):
        if at in self.out_buffer.buffer_data[:,0]:
            i = np.where(self.out_buffer.buffer_data[:,0] == at)
            self.out_buffer.buffer_data[i] = [at, self.out_buffer.level]
        else:
            self.out_buffer.buffer_data = np.append(
                self.out_buffer.buffer_data, 
                [[at, self.out_buffer.level]], 
                axis=0
            )


    def get_health(self, time):
        # returns machine health at a specific time
        time_steps = self.health_data[:,0]
        
        if time in time_steps:
            index = np.where(self.health_data[:,0] == time)[0][0]
        else:
            index = np.searchsorted(time_steps, time) - 1
        
        return self.health_data[index, 1]
