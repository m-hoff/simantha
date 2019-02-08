import simpy
import time
import pandas as pd
from graphviz import Digraph

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
                 initial_buffer=0,

                 failures={'degradation':None, # list 
                           'reliability':None}, # scipy distributions
                 degradation=None, # list or int of degradation rate
                 planned_failures=None, # list of (loc, time, duration)
                 maintenance_policy=None, # CM/PM/CBM, str
                 maintenance_params=None, # define policy
                 maintenance_capacity=1,
                 maintenance_costs=None,
                 debug=False):

        # specified system characteristics
        self.process_times = process_times
        self.interarrival_time = interarrival_time        
        if type(buffer_sizes) == int:
            self.buffer_sizes = [buffer_sizes]*(len(process_times)-1)
        else:
            self.buffer_sizes = buffer_sizes
           
        if type(initial_buffer) == int:
            self.initial_buffer = [initial_buffer]*(len(process_times)-1)
        else:
            self.initial_buffer = initial_buffer
        
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
        self.bottleneck_process_time = max(self.process_times)
        self.bottleneck = self.process_times.index(self.bottleneck_process_time)
        
        self.debug = debug
        
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
                self.buffers += [simpy.Container(self.env, capacity=self.buffer_sizes[m], init=self.initial_buffer[m])]
            
            # planned failures for m
            if self.planned_failures:
                planned_failures_m = [DT for DT in self.planned_failures if DT[0] == m]
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
                    
        self.state_data = pd.DataFrame(columns=state_cols) #TODO: write state data
        self.production_data = pd.DataFrame(columns=prod_cols) #TODO: write production data
        self.machine_data = pd.DataFrame(columns=machine_cols) #TODO: write machine data
        self.queue_data = pd.DataFrame(columns=['time', 'contents']) #TODO: write queue data
        self.maintenance_data = pd.DataFrame(columns=['time',
                                                      'machine',
                                                      'type',
                                                      'activity',
                                                      'duration']) #TODO: write maint data
        self.data = {'state': self.state_data,
                     'production': self.production_data,
                     'machine': self.machine_data,
                     'queue':self.queue_data,
                     'maintenance': self.maintenance_data}
                     
        self.next_for_repair = None             
        
    def simulate(self, title='Simulation',
                 warmup_time=0,
                 sim_time=100,
                 seed=None,
                 verbose=True):
                 
        self.warmup_time = warmup_time
        self.sim_time = sim_time
        
        if self.planned_failures:
            self.planned_failures = [(dt[0], dt[1]+self.warmup_time, dt[2]) for dt in self.planned_failures]
        
        start_time = time.time()
        if seed:
            random.seed(seed)
                          
        self.initialize() # reinitialize system

        for key in self.data.keys():
            self.data[key]['time'] = list(range(-self.warmup_time, self.sim_time))
       
        # run simulation
        self.env.run(until=warmup_time+sim_time)   

        # fill in data frames
        
        self.data['state'].fillna(method='ffill', inplace=True)
        
        self.data['production'].fillna(method='ffill', inplace=True)
        self.data['production'].fillna(0, inplace=True)
        for m in range(self.M):
            TH_col = 'M{} throughput'.format(m)
            self.data['production'][TH_col] = self.data['production']['M{} production'.format(m)]/self.data['production']['time']
                
        self.maintenance_data.dropna(subset=['machine'], inplace=True)
        self.maintenance_data.reset_index(inplace=True, drop=True)
        
        if verbose:
            print('Simulation complete in {:.2f}s'.format(time.time()-start_time))        
            #TODO: print system summary
            
    def draw(self):
        sys = Digraph(comment='System layout')

        # create machine node shape
        sys.attr('node', shape='rectangle', height='0.5', width='0.75')

        # create invisible source node
        sys.node('source', '', style='invis', width='0.1')

        # create node for each machine
        for m in range(self.M):
            Mi = 'M{}'.format(m)

            sys.node(Mi, Mi)

        # create node for each buffer
        sys.attr('node', shape='circle', **{'height':'0.1', 'width':'0.1'})
        for m in range(self.M-1):
            Bi = 'B{}'.format(m)

            sys.node(Bi, Bi)

        # create invisible sink
        sys.node('sink', '', style='invis', width='0.1')

        # add edges to adjacent nodes
        sys.attr('edge', arrowsize='0.65')
        sys.edge('source', 'M0')
        if self.M > 1:
            for m in range(self.M-1):
                sys.edge('M{}'.format(m),'B{}'.format(m))
                sys.edge('B{}'.format(m),'M{}'.format(m+1))
        sys.edge('M{}'.format(self.M-1),'sink')

        sys.graph_attr['rankdir'] = 'LR'

        return sys