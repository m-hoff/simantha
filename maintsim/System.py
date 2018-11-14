import simpy
import time
import pandas as pd

from Machine import Machine
# import Buffer
# import Source
# import Sink

class System:
    '''
    Manufacturing system class
    '''
    def __init__(self,
                 process_times,
                 interarrival_time=1, # int
                 buffer_sizes=1, # list or int

                 failures={'degradation':None, # list 
                           'reliability':None}, # scipy distributions
                 degradation=None, # list or int of degradation rate
                 planned_failures=None, # list of (loc, time, duration)
                 maintenance_policy=None, # CM/PM/CBM, str
                 maintenance_params=None, # define policy
                 maintenance_capacity=1,
                 maintenance_costs=None):

        # specified system characteristics
        self.process_times = process_times
        self.interarrival_time = interarrival_time
        if type(buffer_sizes) == int:
            self.buffer_sizes = [buffer_sizes]*(len(process_times)-1)
        else:
            self.buffer_sizes = buffer_sizes
        self.failures = failures    
        #if type(degradation) == int:
        #    self.degradation = [degradation]*(len(process_times))
        #else:
        #    self.degradation = degradation
        if degradation:
            self.degradation = degradation
        else:
            self.degradation = [0]*len(process_times)
        
        self.planned_failures = planned_failures
        self.maintenance_policy = maintenance_policy
        self.maintenance_params = maintenance_params
        self.maintenance_capacity = maintenance_capacity
        self.maintenance_costs = maintenance_costs

        # inferred system characteristics
        self.M = len(process_times) # number of machines
        self.bottleneck_rate = max(self.process_times)
        self.bottleneck = self.process_times.index(self.bottleneck_rate)
        
        self.initialize() # initialize system objects
        
        # simulation parameters
        self.warmup_time = 0
        
    def initialize(self):
        '''
        Prepares the system for simulation. The system must be 
        reinitialized with a new simpy environment for each 
        iteration of the simulation. 
        '''
    
        # create simpy environment
        self.env = simpy.Environment()
    
        # create repairman object
        self.repairman = simpy.PriorityResource(self.env, capacity=self.maintenance_capacity)
    
        # create source object
    
        # create objects for each machine
        self.buffers = []
        self.machines = []
        
        for m in range(self.M):
            # buffer objects
            if m < (self.M - 1):
                self.buffers += [simpy.Container(self.env, capacity=self.buffer_sizes[m])]
            
            # planned failures for m
            if self.planned_failures:
                planned_falures_m = [DT for DT in self.planned_failures if DT[0] == m]
            else:
                planned_failures_m = []
            
            # machine objects
            process_time = self.process_times[m]
            self.machines += [Machine(self.env, m, process_time, self.degradation[m],
                                      planned_failures_m, self, self.repairman)]

                                      
        # initialize system data collection
        state_cols = ['time']     # system state data
        prod_cols = ['time']      # production data
        machine_cols = ['time']   # machine status data
        
        
        for machine in self.machines:
            state_cols += [machine.name + ' has part']
            if machine.m < (self.M - 1):
                state_cols += ['b{} level'.format(machine.m)]
                
            prod_cols += [machine.name+' production', machine.name+' throughput']
                
            machine_cols += [machine.name+' functional', machine.name+' forced idle']
            
            
        self.state_data = pd.DataFrame(columns=state_cols)
        self.production_data = pd.DataFrame(columns=prod_cols)
        self.machine_data = pd.DataFrame(columns=machine_cols)        
        self.queue_data = pd.DataFrame(columns=['time', 'contents'])
        self.maintenance_data = pd.DataFrame(columns=['time',
                                                      'machine',
                                                      'type',
                                                      'activity',
                                                      'duration'])
        
    def simulate(self, title='Simulation',
                 warmup_time=0,
                 sim_time=100,
                 seed=None,
                 verbose=True):
        
        start_time = time.time()
        if seed:
            random.seed(seed)
            
        self.initialize()
        
        self.env.run(until=warmup_time+sim_time)   

        if verbose:
            print('Simulation complete in {:.2f}s'.format(time.time()-start_time))                                               