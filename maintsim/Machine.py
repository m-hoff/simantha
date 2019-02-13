import simpy
import pandas as pd
from random import random

class Machine:
    def __init__(self, 
                 env, 
                 m, 
                 process_time, 
                 #degradation, 
                 planned_failures,
                 failure_mode,
                 failure_params,
                 system, 
                 repairman):
                 
        self.env = env
        self.m = m
        self.name = 'M{}'.format(self.m)
        
        self.process_time = process_time
        
        #self.degradation = degradation
        self.planned_failures = planned_failures
        self.failure_mode = failure_mode
        if self.failure_mode == 'degradation': # Markov degradation
            self.degradation = failure_params
        else: # TTF distribution
            self.ttf_dist = failure_params
            
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
        
        self.process = self.env.process(self.working(self.system.repairman))
        if self.failure_mode == 'degradation':
            self.env.process(self.degrade(self.system.repairman))
        elif self.failure_mode == 'reliability':
            self.env.process(self.reliability())
        #self.env.process(self.maintain())
        
        if self.system.debug:
            self.env.process(self.debug_process())
                
    def debug_process(self):
    #TODO: use a similar process to write data
        while True:
            try:
                if self.m == 0:
                    print('R_0({})={}'.format(self.env.now, self.remaining_process_time))
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
                #if self.m==0: print('working...t={}'.format(self.env.now))
                idle_start = idle_stop = 0
                
                # get part from input buffer
                if self.m > 0: 
                    #self.write_data()
                    idle_start = self.env.now - self.system.warmup_time
                    #while self.in_buff.level == 0:
                        #yield self.env.timeout(1)
                        #self.write_state()
                        
                    yield self.in_buff.get(1)
                    self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m-1)] = self.in_buff.level
                    
                    #print('M{} got part from buffer at {}, b={}'.format(self.m, self.env.now, self.in_buff.level))
                                       
                    idle_stop = self.env.now - self.system.warmup_time

                self.has_part = True
                
                self.system.state_data.loc[self.env.now, self.name+' has part'] = 1
                 
                self.remaining_process_time = self.process_time
                    
                # check if machine was starved
                if idle_stop - idle_start > 0:
                    #if self.m == 1: print('M{} starved from t={} to t={}'.format(self.m, idle_start, idle_stop))
                    self.system.machine_data.loc[idle_start:idle_stop-1, 
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
                    idle_start = self.env.now - self.system.warmup_time
                    #while self.out_buff.level >= self.out_buff.capacity:
                        #yield self.env.timeout(1)
                        #self.write_state()
                        
                    yield self.out_buff.put(1)
                    self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m)] = self.out_buff.level
                    
                    #print('M{} put part in buffer at {}, b={}'.format(self.m, self.env.now, self.out_buff.level))
                    
                    idle_stop = self.env.now - self.system.warmup_time
                
                if self.env.now > self.system.warmup_time:
                    self.parts_made += 1
                self.system.production_data.loc[self.env.now, 'M{} production'.format(self.m)] = self.parts_made
                
                #print('Prod', self.env.now, self.m, self.parts_made)
                self.has_part = False
                    
                # check if machine was blocked
                if idle_stop - idle_start > 0:
                    self.system.machine_data.loc[idle_start:idle_stop-1, 
                                                 self.name+' forced idle'] = 1
                    #if self.m == 1: print('M{} blocked from t={} to t={}'.format(self.m, idle_start, idle_stop))
                                      
                #TODO: idle time is not recorded if failure occurs during starvation or blockage

                                
                # TODO: record parts made
                prev_part = self.env.now
                                
            except simpy.Interrupt: 
                # processing interrupted due to failure
                if self.failed:
                    # create maintenance request (after stopping production)
                    self.maintenance_request = self.system.repairman.request(priority=1)
                    yield self.maintenance_request
                    
                self.broken = True
                self.has_part = False
                
                # TODO: fix this
                #time_to_repair = 10
                
                # check if part was finished before failure occured                
                if self.remaining_process_time == 1: 
                    if self.m == self.system.M-1:
                        if self.env.now > self.system.warmup_time:
                            self.parts_made += 1
                    elif self.out_buff.level < self.out_buff.capacity:
                    # part was finished before failure
                        if self.m < self.system.M-1:
                            #idle_start = self.env.now - self.system.warmup_time
                            
                            yield self.out_buff.put(1)
                            self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m)] = self.out_buff.level
                        
                        if self.env.now > self.system.warmup_time:
                            self.parts_made += 1
                        
                    self.system.production_data.loc[self.env.now, 'M{} production'.format(self.m)] = self.parts_made
                        
                    self.has_part = False
                    
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
                #with self.system.repairman.request(priority=1) as req:
                #    print('Request made by M{} at t={}'.format(self.m, self.env.now))
                #    yield req
                #    print('Request granted to M{} at t={}'.format(self.m, self.env.now))
                
                self.time_to_repair = 10
                
                yield self.env.timeout(self.time_to_repair)
                #for t in range(self.time_to_repair):
                #    yield self.env.timeout(1)
                        #print(self.system.repairman.users)
                    # TODO: record maintenance data
                    
                # repairman is released
                self.system.repairman.release(self.maintenance_request)
                
                self.health = 0
                self.failed = False
                self.broken = False
                self.in_maintenance_queue = False
                
                maintenance_stop = self.env.now
                
                self.system.machine_data.loc[maintenance_start:maintenance_stop-1, 'M{} functional'.format(self.m)] = 0
                
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
    
    def reliability(self):
        '''
        Machine failures based on TTF distribution
        '''
                
        while True:
            # check for planned failures
            for failure in self.planned_failures:
                #TODO: make this a method
                if failure[1] == self.env.now:
                    self.time_to_repair = failure[2]
                    self.repair_type = 'planned'
                    '''
                    Here we create a maintenance request without interrupting
                    the machine's processing. The process is only interrupted
                    once it seizes a maintenance resource and the job begins.
                    '''                   
                    #THIS METHOD WORKS
                    self.maintenance_request = self.system.repairman.request(priority=1)
                    
                    yield self.maintenance_request # wait for repairman to become available
                    self.process.interrupt()
                    
            if not self.failed:
                # generate TTF
                ttf = self.ttf_dist.rvs()
                yield self.env.timeout(ttf)
                self.failed = True
                self.repair_type = 'CM'
                
                self.process.interrupt()
            else:
                yield self.env.timeout(1) #TODO: check the placement of this
            
    def degrade(self, repairman):
        '''
        Discrete state Markovian degradation process. 
        '''
        while True:
            # TODO: incorporate markov chain degradation
            while random() > self.degradation:
                # do NOT degrade
                yield self.env.timeout(1)
                
                #check planned failures
                for failure in self.planned_failures:
                    if failure[1] == self.env.now:
                        self.time_to_repair = failure[2]
                        self.repair_type = 'planned'
                        '''
                        Here we create a maintenance request without interrupting
                        the machine's processing. The process is only interrupted
                        once it seizes a maintenance resource and the job begins.
                        '''                   
                        #THIS METHOD WORKS
                        self.maintenance_request = self.system.repairman.request(priority=1)
                        
                        yield self.maintenance_request # wait for repairman to become available
                        self.process.interrupt()
            
            # degrade by one unit once loop breaks
            yield self.env.timeout(1)
            
            if self.health < 10:
                # machine is NOT failed
                self.health += 1
                #if self.m == 0: print('t={}'.format(self.env.now), self.health)
                
                if self.health == 10: # machine fails
                    self.failed = True
                    self.repair_type = 'CM'
                    
                    # record complete failure start
                    #self.system.maintenance_data.loc[self.env.now, 'machine'] = self.m
                    #self.system.maintenance_data.loc[self.env.now, 'type'] = 'CM'
                    #self.system.maintenance_data.loc[self.env.now, 'activity'] = 'failure'
                    
                    self.in_maintenance_queue = True
                    self.time_to_repair = 10 #TODO: fix this
                    self.process.interrupt()
                    
                elif (self.maintenance_policy == 'CBM') and (self.health == self.CBM_threshold):
                    # hit CBM threshold, schedule maintenance
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
                        
    def maintain(self):
        while True:
            # check for planned failures
            for failure in self.planned_failures:
                if failure[1] == self.env.now:
                    self.time_to_repair = failure[2]
                    self.repair_type = 'planned'
                    self.failed = True
                    print('Calling planned failure on M{}'.format(self.m))
                    self.process.interrupt()
            
            if self.health == 10:
                self.failed = True
                self.repair_type = 'CM'
                self.time_to_repair = 10
                print('Calling corrective failure on M{} at t={}'.format(self.m, self.env.now))
                self.process.interrupt()
            elif self.maintenance_policy == 'CBM':
                if self.health == self.CBM_threshold:
                    self.maintenance_request = self.system.repairman.request(priority=1)
                    yield self.maintenance_request
                    self.repair_type = 'CBM'
                    self.process.interrupt()
            
            yield self.env.timeout(1)