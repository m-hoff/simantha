import time

import numpy as np
from scipy import stats
import simpy

print_debug = False

class Machine:    
    def __init__(
        self, 
        env, 
        system, 
        index, 
        cycle_time, 
        in_buffer=None, 
        out_buffer=None, 
        degradation_matrix=np.eye(2), 
        maintenance_threshold=999,
        repairman=None, 

        initial_health=0, 
        initial_remaining_process=None
    ):
        self.env = env
        self.system = system
        
        self.index = index
        
        self.cycle_time = cycle_time
        self.in_buffer = in_buffer
        self.out_buffer = out_buffer
        self.degradation_matrix = degradation_matrix
        self.failed_state = degradation_matrix.shape[0] - 1

        # maintenance parameters
        self.maintenance_threshold = min(
            [self.failed_state, maintenance_threshold]
        )
        
        # production state
        self.parts_made = 0
        if initial_remaining_process == cycle_time:
            self.remaining_processing_time = initial_remaining_process
            self.has_part = False
        elif initial_remaining_process:
            self.remaining_processing_time = initial_remaining_process
            self.has_part = True
        else:
            self.remaining_processing_time = cycle_time
            self.has_part = False
        
        # maintenance state
        self.health = initial_health
        self.health_data = np.array([[self.env.now, self.health]])
        self.maintenance_state = 'healthy' # healthy, unhealthy, failed
        
        if self.health >= self.maintenance_threshold:
            self.in_queue = True
        else:
            self.in_queue = False

        self.ttq = -1
        self.ttqs = []
        self.ttq_timestamp = -1

        self.ttf = -1
        self.ttfs = []
        self.ttf_timestamp = -1

        self.failed = False
        self.under_repair = False
        self.repair_type = None
        self.time_entered_queue = np.inf
        self.repairman = repairman
        self.repair_event = self.env.event()
        
        # machine data
        self.production_data = []
        self.maintenance_data = []
        
        # main simpy processes
        self.production_process = self.env.process(self.production())
        self.degradation_process = self.env.process(self.degradation())

    def production(self):
        '''
        Continuously produces parts until interrupted by repair or failure. 
        '''
        while True:
            try:
                if self.in_buffer and (not self.has_part):
                    yield self.in_buffer.get(1)
                    #self.update_in_buffer_data(self.env.now)
                self.has_part = True
                
                while self.remaining_processing_time:
                    # need to timeout by 1 to capture machine state
                    yield self.env.timeout(1)
                    self.remaining_processing_time -= 1
                
                if self.out_buffer:
                    yield self.out_buffer.put(1)
                    self.update_out_buffer_data(self.env.now)
                self.has_part = False
                self.remaining_processing_time = self.cycle_time
                
                if self.env.now >= self.system.warm_up_time:
                    self.parts_made += 1
                    #self.production_data.append(
                    #    [self.env.now-self.system.warm_up_time, self.parts_made]
                    #)

            except simpy.Interrupt:
                if not self.repair_event.triggered:
                    yield self.repair_event # wait for repair to finish

                    self.repair_event = self.env.event()
                    self.degradation_process = self.env.process(self.degradation())
            
                    self.system.repairman.schedule_maintenance()       


    def degradation(self):
        '''
        Process for machine degradation and failure. ttq/ttf is the time until
        entering the maintenance queue/failing. ttq_timestamp/ttf_timestamp is 
        the simulation time at which these events occur. 
        '''
        try:
            # get time to degrade by 1 health unit
            time_to_degrade = self.get_time_to_degrade()
            yield self.env.timeout(time_to_degrade)
            self.health += 1

            # check for machine failure
            if self.health == self.failed_state:
                self.failed = True
                self.repair_type = 'corrective'
                if not self.in_queue:
                    self.time_entered_queue = self.env.now
                    self.in_queue = True
                self.production_process.interrupt()

            # schedule for maintnance if health exceeds CBM threshold
            elif self.health >= self.maintenance_threshold:
                self.repair_type = 'preventive'
                if not self.in_queue:
                    self.time_entered_queue = self.env.now
                    self.in_queue = True

            self.system.repairman.schedule_maintenance()
        
        except simpy.Interrupt:
            # degradation interrupted if maintenance is scheduled before failure
            try:
                yield self.repair_event
            except:
                pass

    def repair(self, healths=None):
        if healths is not None:
            for i, machine in enumerate(self.system.machines):
                machine.health = healths[i]
        self.system.debug=True
        self.in_queue = False
        self.under_repair = True

        self.system.repairman.update_queue_data()

        #self.maintenance_request = self.system.repairman.request(priority=1)
        if self.repair_type == 'preventive':
            try:
                self.degradation_process.interrupt()
            except:
                pass
            self.production_process.interrupt()

        # clear health data beyond this point
        self.health_data = self.health_data[self.health_data[:,0] < self.env.now]

        ttr = self.get_time_to_repair()
        self.maintenance_data.append(
            [self.env.now-self.system.warm_up_time, self.repair_type, ttr]
        )

        yield self.env.timeout(ttr)

        self.health = 0 # machine completely restored
        self.update_health_data(at=self.env.now)

        self.failed = False
        self.under_repair = False
        self.remaining_processing_time = self.cycle_time

        self.ttq = -1
        self.ttf = -1

        if not self.repair_event.triggered:
            self.repair_event.succeed()
        self.system.repairman.utilization -= 1 # release repairman


    def get_time_to_repair(self):
        '''
        Generate time to repair depending on repair type. 
        '''
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

        return ttr


    def get_time_to_degrade(self):
        if (1 in np.diagonal(self.degradation_matrix)[:-1]):
            ttd = np.inf
        else:
            ttd = 0
            current_health = new_health = self.health
            all_states = np.arange(self.failed_state + 1)
            while new_health == current_health:
                new_health = np.random.choice(
                    all_states, p=self.degradation_matrix[int(new_health)]
                )
                ttd += 1
        
        return ttd


    def get_time_to_queue(self):
        '''
        Generate the time until entering the maintenance queue. If the machine
        cannot reach the failed state (according to the transition matrix), or
        is not allowed to fail, TTQ is infininte. 
        '''
        if (1 in np.diagonal(self.degradation_matrix)[:-1]):
            ttq = np.inf
        else:
            ttq = 0
            while self.health < self.maintenance_threshold:
                previous_health = self.health
                all_states = np.arange(self.failed_state + 1)
                #print(self.index, self.health)
                self.health = np.random.choice(
                    all_states, p=self.degradation_matrix[int(self.health)]
                )
                if self.health != previous_health:
                    self.update_health_data(at=self.env.now+ttq)
                ttq += 1

        return ttq
    
    def get_time_to_failure(self):
        '''
        Generate the time until machine failure. If the machine cannot reach the
        failed state (according to the transition matrix), or is not allowed to
        fail, TTQ is infininte. 
        '''        
        if (
            (1 in np.diagonal(self.degradation_matrix)[:-1])
            or (not self.in_queue)
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
                    all_states, p=self.degradation_matrix[int(self.health)]
                )
                if self.health != previous_health:
                    self.update_health_data(at=self.env.now+ttf)
                ttf +=1

        return ttf

    
    def update_health_data(self, at=None):
        '''
        Store health data of the machine including the time of each health state
        transition. 
        '''
        self.health_data = self.health_data[self.health_data[:,0] < at]

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
        '''
        Get the health of the machine at a specific time based on the recorded
        health data. 
        '''
        try:
            time_steps = self.health_data[:,0]
            
            if time in time_steps:
                index = np.where(self.health_data[:,0] == time)[0][0]
            else:
                index = np.searchsorted(time_steps, time) - 1
            return self.health_data[index, 1]
        except:
            return 0


    def get_production(self, time):
        '''
        Get the production count of the machine at a specific time based on the 
        recorded production data. 
        '''
        production_arr = np.array(self.production_data)
        time_steps = production_arr[:,0]

        if time in time_steps:
            index = np.where(production_arr[:,0] == time)[0][0]
        else:
            index = np.searchsorted(time_steps, time) - 1

        return production_arr[index, 1]
