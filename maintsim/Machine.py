import simpy
import pandas as pd
from random import random

class Machine:
    '''
    Machine object. Processes discrete parts while not failed or under repair.
    '''
    def __init__(self, 
                 env, 
                 m, 
                 process_time,
                 planned_failures,
                 failure_mode,
                 failure_params,
                 initial_health,
                 system):
                 
        self.env = env
        self.system = system
        self.m = m
        self.name = 'M{}'.format(self.m)
        
        self.process_time = process_time
        
        self.planned_failures = planned_failures
        self.failure_mode = failure_mode
        if self.failure_mode == 'degradation': # Markov degradation
            self.degradation = failure_params
        
        # determine maintenance policy for machine
        self.maintenance_policy = self.system.maintenance_policy
        maintenance_parameters = self.system.maintenance_params
        if self.maintenance_policy == 'CBM':
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
        self.health = initial_health
        self.last_repair_time = None
        self.failed = False
        self.repair_type = None
        self.request_preventive_repair = False
        self.under_repair = False
        # production state
        self.idle = True
        self.has_part = False
        self.remaining_process_time = self.process_time
        self.parts_made = 0
        self.total_downtime = 0 # blockage + startvation + repairs
        
        self.process = self.env.process(self.working())
        if self.failure_mode == 'degradation':
            # start Markovian degradation process
            self.failing = self.env.process(self.degrade())
        # self.env.process(self.maintain())
        
        self.maintenance = self.env.process(self.maintain())

        if self.system.debug:
            self.env.process(self.debug_process())
                
    def debug_process(self):
        '''
        Process that will loop once per simulation time step. 
        '''
        while True:
            try:
                if (self.m == 1):
                    #print('t={}, r={}'.format(self.env.now, self.system.repairman.count))
                    print('{}'.format(self.env.now),
                          self.system.repairman.get_queue, 
                          self.system.repairman.users,
                          self.system.repairman.put_queue)
                #else:
                #    print(self.health)
                yield self.env.timeout(1)
                
            except simpy.Interrupt:
                pass

    def working(self):
        '''
        Main production function. Machine will process parts until interrupted 
        by failure. A maintenance job will be carried out at the interruption
        of production.
        '''
        while True:
            try:
                self.idle_start = self.idle_stop = self.env.now
                self.idle = True
                
                # get part from input buffer
                if self.m > 0:
                    yield self.in_buff.get(1)                    
                    self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m-1)] = self.in_buff.level
                    
                    self.idle_stop = self.env.now
                    
                self.has_part = True
                self.idle = False
                
                #self.system.state_data.loc[self.env.now, self.name+' has part'] = 1
                 
                self.remaining_process_time = self.process_time
                    
                # check if machine was starved
                if self.idle_stop - self.idle_start > 0:
                    #if self.m == 1: print('M{} starved from t={} to t={}'.format(self.m, self.idle_start, self.idle_stop))                  
                    self.system.machine_data.loc[self.idle_start:self.idle_stop-1, 
                                                 self.name+' forced idle'] = 1
                    
                    if self.env.now > self.system.warmup_time:       
                        self.total_downtime += (self.idle_stop - self.idle_start)
                
                # process part
                for _ in range(self.process_time):
                    self.system.state_data.loc[self.env.now, self.name+' R(t)'] = self.remaining_process_time
                    yield self.env.timeout(1)
                    
                    self.remaining_process_time -= 1
                                            
                # put finished part in output buffer
                self.idle_start = self.env.now
                self.idle = True
                if self.m < self.system.M-1:
                    yield self.out_buff.put(1) 
                    self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m)] = self.out_buff.level                    

                    self.idle_stop = self.env.now
                    self.idle = False
                
                if self.env.now > self.system.warmup_time:
                    self.parts_made += 1
                    
                self.system.production_data.loc[self.env.now, 'M{} production'.format(self.m)] = self.parts_made
                
                self.has_part = False
                
                # check if machine was blocked
                if self.idle_stop - self.idle_start > 0:
                    #if self.m == 1: print('M{} blocked from t={} to t={}'.format(self.m, self.idle_start, self.idle_stop))
                    self.system.machine_data.loc[self.idle_start:self.idle_stop-1, 
                                                 self.name+' forced idle'] = 1
                    if self.env.now > self.system.warmup_time:
                        self.total_downtime += (self.idle_stop - self.idle_start)
                                
            except simpy.Interrupt: 
                self.under_repair = True 
                self.failing.interrupt() # stop degradation during maintenance                

                failure_start = self.env.now
                if self.failed:
                    self.maintenance.interrupt()
                    try:
                        self.maintenance_request.cancel() # cancel preventive request
                    except:
                        pass

                    fail_time = self.env.now - self.system.warmup_time
                    # create new corrective request (after stopping production)
                    self.maintenance_request = self.system.repairman.request(priority=1)
                    yield self.maintenance_request                    
                    
                self.has_part = False
                # check if part was finished before failure occured                
                if (self.system.M > 1) and (self.system.state_data.loc[self.env.now-1, 'M{} R(t)'.format(self.m)] == 1):                    
                    # I think this works. Might need further valifation
                    if self.m == self.system.M-1:
                        if self.env.now > self.system.warmup_time:
                            self.parts_made += 1
                    elif self.out_buff.level < self.out_buff.capacity:
                    # part was finished before failure                        
                        if self.m < self.system.M-1:
                            yield self.out_buff.put(1)
                            self.system.state_data.loc[self.env.now, 'b{} level'.format(self.m)] = self.out_buff.level
                        
                        if self.env.now > self.system.warmup_time:
                            self.parts_made += 1
                        
                    self.system.production_data.loc[self.env.now, 'M{} production'.format(self.m)] = self.parts_made
                        
                    self.has_part = False
                    
                maintenance_start = self.env.now
               
                # write failure data
                if self.last_repair_time:
                    TTF = self.env.now - self.last_repair_time
                else:
                    TTF = 'NA'
                
                if not self.failed:
                    fail_time = self.env.now - self.system.warmup_time

                new_failure = pd.DataFrame({'time':[fail_time],
                                            'machine':[self.m],
                                            'type':[self.repair_type],
                                            'activity':['failure'],
                                            'duration':[TTF]})
                self.system.maintenance_data = self.system.maintenance_data.append(new_failure, ignore_index=True) 

                #TODO: get priority
                
                # generate TTR based on repair type
                if self.repair_type is not 'planned':
                    self.time_to_repair = self.system.repair_params[self.repair_type].rvs()
                
                # wait for repair to finish
                for _ in range(self.time_to_repair):
                    yield self.env.timeout(1)
                    # record queue data
                    self.system.queue_data.loc[self.env.now, 'contents'] = len(self.system.repairman.queue)

                # repairman is released
                self.system.repairman.release(self.maintenance_request)
                
                self.health = 0
                self.last_repair_time = self.env.now
                self.failed = False
                self.under_repair = False

                # record restored health
                self.system.machine_data.loc[self.env.now, self.name+' health'] = self.health
                
                maintenance_stop = self.env.now
                
                self.system.machine_data.loc[maintenance_start:maintenance_stop-1, 'M{} functional'.format(self.m)] = 0
                
                # write repair data
                new_repair = pd.DataFrame({'time':[self.env.now-self.system.warmup_time],
                                           'machine':[self.m],
                                           'type':[self.repair_type],
                                           'activity':['repair'],
                                           'duration':[maintenance_stop-maintenance_start]})
                self.system.maintenance_data = self.system.maintenance_data.append(new_repair)
                
                failure_stop = self.env.now
                
                if self.env.now > self.system.warmup_time:       
                    self.total_downtime += (failure_stop - failure_start)
                
                # machine was idle before failure                
                self.system.machine_data.loc[self.idle_start:failure_stop-1, 
                                             self.name+' forced idle'] = 1
                #if self.m == 1: print('M{} down for maint from t={} to t={}'.format(self.m, self.idle_start, failure_stop))
            
    def degrade(self):
        '''
        Discrete state Markovian degradation process. 
        '''
        while True:
            try:
                #print('degradation resumed at t={}'.format(self.env.now))
                while random() > self.degradation:
                    # do not degrade
                    yield self.env.timeout(1)
                
                # degrade by one unit once loop breaks
                yield self.env.timeout(1)
                
                if self.health < 5: # machine is NOT failed
                    self.health += 1 # degrade by one unit

                    # record current machine health
                    self.system.machine_data.loc[self.env.now, self.name+' health'] = self.health
                    
                    if self.health == 5: # machine fails
                        self.failed = True
                        self.repair_type = 'CM'
                        #self.need_repair = True
                        
                        #self.system.repairman.release(self.maintenance_request)
                        self.process.interrupt()
                        
                    if (self.maintenance_policy == 'CBM') and (self.health == self.CBM_threshold) and (not self.failed):
                        # CBM threshold reached, request repair, assumes each degradation state is visited
                        self.request_preventive_repair = True
                        self.repair_type = 'CBM'
            except simpy.Interrupt:
                # stop degradation process while machine is under repair
                while self.under_repair:
                    yield self.env.timeout(1)            

    def maintain(self):
        '''
        Process for scheduling maintenance by generating maintenance resource
        requests.
        '''
        while True:
            try:
                # check if a failure is planned
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
                        self.failing.interrupt()
                        self.process.interrupt()

                # check if a repair is requested
                if self.request_preventive_repair:
                    self.request_preventive_repair = False
                    self.maintenance_request = self.system.repairman.request(priority=1)                    
                    yield self.maintenance_request # request PM            
                    
                    self.process.interrupt() # request granted, interrupt production
                yield self.env.timeout(1)

            except simpy.Interrupt:
                while self.under_repair:
                    yield self.env.timeout(1)