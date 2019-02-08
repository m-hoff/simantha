import simpy
import pandas as pd
from random import random

from Globals import G

class Machine:
    def __init__(self, 
                 env, 
                 m, 
                 process_time, 
                 degradation, 
                 planned_failures,
                 system, 
                 repairman):
                 
        self.env = env
        self.m = m
        self.name = 'M{}'.format(self.m)
        self.process_time = process_time
        self.degradation = degradation
        self.planned_failures = planned_failures
        self.system = system
        self.repairman = repairman
        
        # determine maintenance policy for machine
        self.maintenance_policy = self.system.maintenance_policy
        maintenance_parameters = self.system.maintenance_params
        if self.maintenance_policy == 'PM':
            self.PM_interval = maintenance_parameters['PM interval'][self.m]
            self.PM_duration = maintenance_parameters['PM duration'][self.m]
        elif self.maintenance_policy == 'CBM':
            self.CBM_threshold = maintenance_parameters['CBM threshold'][self.m]
        # 'None' maintenance policy == 'CM'
        
        # assign input buffer
        if self.m > 0:
            self.in_buff = self.system.buffers[self.m-1]
            
        # assign output buffer
        if (self.m < self.system.M-1):
            self.out_buff = self.system.buffers[m]
        
        # set initial machine state
        # maintenance state
        self.health = 0 # starts in perfect health
        self.in_maintenance_queue = False
        self.failed = False
        self.repair_type = None
        # production state
        self.has_part = False
        self.remaining_process_time = self.process_time
        self.parts_made = 0
        
        self.process = self.env.process(self.working(self.repairman))
        self.env.process(self.degrade())
        #self.env.process(self.record_data())
        
        if self.system.debug:
            self.env.process(self.debug_process())
                
    def debug_process(self):
    #TODO: use a similar process to write data
        while True:
            try:
                if self.m == 0:
                    print(self.repairman.count)
                yield self.env.timeout(1)
                
            except simpy.Interrupt:
                pass
                
    def record_data(self):
        '''
        Record simulation data at each time step.
        '''
        while True:
            try:
                t = self.env.now 
                
                # machine/buffer contents
                if self.has_part:
                    self.system.state_data.loc[t, self.name+' has part'] = 1
                else:
                    self.system.state_data.loc[t, self.name+' has part'] = 0
                
                if self.m < (self.system.M - 1): # not the last machine
                    level = self.out_buff.level
                    self.system.state_data.loc[t, 'b'+str(self.m)+' level'] = level
                
                # production data
                self.system.production_data.loc[t, 'M{} production'.format(self.m)] = self.parts_made
                
                yield self.env.timeout(1)
                
            except simpy.Interrupt:
                pass
                
    def working(self, repairman):
        '''
        Main production function. Machine will produce parts
        until interrupted by failure. 
        '''
        prev_part = 0
        while True:
            try:
                idle_start = idle_stop = 0
                
                # get part from input buffer
                if self.m > 0: 
                    #self.write_data()
                    idle_start = self.env.now - G.warmup_time
                    #while self.in_buff.level == 0:
                        #yield self.env.timeout(1)
                        #self.write_state()
                        
                    yield self.in_buff.get(1)
                    self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m-1)] = self.in_buff.level
                    
                    #print('M{} got part from buffer at {}, b={}'.format(self.m, self.env.now, self.in_buff.level))
                                       
                    idle_stop = self.env.now - G.warmup_time

                self.has_part = True
                
                self.system.state_data.loc[self.env.now, self.name+' has part'] = 1
                                                                        
                self.remaining_process_time = self.process_time
                    
                # check if machine was starved
                if idle_stop - idle_start > 0:
                    #print('M{} idle at time {}'.format(self.m, self.env.now))
                    self.system.machine_data.loc[idle_start:idle_stop, 
                                                 self.name+' forced idle'] = 1
                    
                # process part
                for t in range(self.process_time):
                    # TODO: record processing
                    #self.write_state()
                                       
                    yield self.env.timeout(1)
                    self.remaining_process_time -= 1
                                                            
                # put finished part in output buffer
                idle_start = idle_stop = 0
                if self.m < self.system.M-1:
                    idle_start = self.env.now - G.warmup_time
                    #while self.out_buff.level >= self.out_buff.capacity:
                        #yield self.env.timeout(1)
                        #self.write_state()
                        
                    yield self.out_buff.put(1)
                    self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m)] = self.out_buff.level
                    
                    #print('M{} put part in buffer at {}, b={}'.format(self.m, self.env.now, self.out_buff.level))
                    
                    idle_stop = self.env.now - G.warmup_time
                
                if self.env.now > self.system.warmup_time:
                    self.parts_made += 1
                self.system.production_data.loc[self.env.now, 'M{} production'.format(self.m)] = self.parts_made
                
                #print('Prod', self.env.now, self.m, self.parts_made)
                self.has_part = False
                    
                # check if machine was blocked
                if idle_stop - idle_start > 0:
                    self.system.machine_data.loc[idle_start:idle_stop, 
                                                 self.name+' forced idle'] = 1
                    #print('M{} idle at time {}'.format(self.m, self.env.now))
                                      
                #if self.env.now > G.warmup_time:

                                
                # TODO: record parts made
                prev_part = self.env.now
                                
            except simpy.Interrupt: 
                # processing interrupted due to failure
                self.broken = True
                self.has_part = False
                
                # TODO: fix this
                #time_to_repair = 10
                
                maintenance_start = self.env.now
                
                # write failure data
                new_failure = pd.DataFrame({'time':[self.env.now-self.system.warmup_time],
                                            'machine':[self.m],
                                            'type':[self.repair_type],
                                            'activity':['failure'],
                                            'duration':['']})
                self.system.maintenance_data = self.system.maintenance_data.append(new_failure, ignore_index=True) 
                                            
                
                #self.system.maintenance_data.loc[self.env.now, 'time'] = self.env.now
                #self.system.maintenance_data.loc[self.env.now, 'machine'] = self.m
                #self.system.maintenance_data.loc[self.env.now, 'type'] = self.repair_type
                #self.system.maintenance_data.loc[self.env.now, 'activity'] = 'failure'
                                
                # TODO: get priority
                with repairman.request(priority=1) as req:
                    yield req
                    yield self.env.timeout(self.time_to_repair)
                    # TODO: record maintenance data
                    
                    # repairman is released
                                    
                self.health = 0
                self.broken = False
                self.in_maintenance_queue = False
                
                maintenance_stop = self.env.now
                
                self.system.machine_data.loc[maintenance_start:maintenance_stop, 'M{} functional'.format(self.m)] = 0
                
                # write repair data
                new_repair = pd.DataFrame({'time':[self.env.now-self.system.warmup_time],
                                           'machine':[self.m],
                                           'type':[self.repair_type],
                                           'activity':['repair'],
                                           'duration':[maintenance_stop-maintenance_start]})
                self.system.maintenance_data = self.system.maintenance_data.append(new_repair)
                
                #self.system.maintenance_data.loc[self.env.now, 'machine'] = self.m
                #self.system.maintenance_data.loc[self.env.now, 'type'] = self.repair_type
                #self.system.maintenance_data.loc[self.env.now, 'activity'] = 'repair'
                #self.system.maintenance_data.loc[self.env.now, 'duration'] = maintenance_stop - maintenance_start
                
                # TODO: record more maintenance data
    
    def degrade(self):
        '''
        Discrete state degradation process. 
        '''
        while True:
            # TODO: incorporate markov chain degradation
            while random() > self.degradation:
                # do NOT degrade
                yield self.env.timeout(1)
                # TODO: check planned failures
                for failure in self.planned_failures:
                    if failure[1] == self.env.now:
                        #print('Planned failure on {} at {} for {}'.format(self.m, self.env.now, failure[2]))
                        self.time_to_repair = failure[2]
                        self.repair_type = 'planned'
                        self.process.interrupt()
            
            # degrade by one unit once loop breaks
            yield self.env.timeout(1)
            
            if self.health < 10:
                # machine is NOT failed
                self.health += 1
                
                if self.health == 10: # machine fails
                    self.failed = True
                    self.repair_type = 'CM'
                    
                    # record complete failure start
                    #self.system.maintenance_data.loc[self.env.now, 'machine'] = self.m
                    #self.system.maintenance_data.loc[self.env.now, 'type'] = 'CM'
                    #self.system.maintenance_data.loc[self.env.now, 'activity'] = 'failure'
                    
                    self.in_maintenance_queue = True
                    self.time_to_repair = 10
                    self.process.interrupt()
                    
                elif (self.maintenance_policy == 'CBM') and (self.health == self.CBM_threshold):
                    # TODO schedule preventive maintenance
                    self.repair_type = 'CBM'
                    
                    # record CBM "failure"
                    print('CBM failure on {} at {}'.format(self.m, self.env.now))
                    print('health={}'.format(self.health))
                    self.system.maintenance_data.loc[self.env.now, 'machine'] = self.m
                    self.system.maintenance_data.loc[self.env.now, 'type'] = 'CBM'
                    self.system.maintenance_data.loc[self.env.now, 'activity'] = 'failure'
                    
                    self.in_maintenance_queue = True
                    #self.process.interrupt()
                #print(self.repairman.count)
                if (self.maintenance_policy == 'CBM') and (self.health >= self.CBM_threshold) and (not self.failed):
                    if self.repairman.count == 0:
                        # only interrupt processing if repairman available
                        #print('M{} calling repairman at {}'.format(self.m, self.env.now))
                        self.process.interrupt()
                                                
    
    def write_data(self):
        self.write_state()
    
    def write_state(self):
        '''
        Record the system state for this machine when called.
        '''
        t = self.env.now
        
        #if self.m == 1:
        #    print('Writing M1 state at t={}, state={}'.format(self.env.now, int(self.has_part)))
        
        # machine status
        if self.has_part:
            self.system.state_data.loc[t, self.name+' has part'] = 1
        else:
            self.system.state_data.loc[t, self.name+' has part'] = 0
        
        #self.system.production_data.loc[t, self.name+' production'] = self.parts_made
        
        #if self.failed:
        #    self.system.machine_data.loc[t, self.name+' functional'] = 0
        #else:
        #    self.system.machine_data.loc[t, self.name+' functional'] = 1
            
        
        
        # buffer status
        if self.m < (self.system.M - 1): # not the last machine
            level = self.out_buff.level
            self.system.state_data.loc[t, 'b'+str(self.m)+' level'] = level
        