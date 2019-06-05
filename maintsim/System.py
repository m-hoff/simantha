import simpy

import time
import random
import numpy as np
import pandas as pd
from graphviz import Digraph

from .Machine import Machine
from .Scheduler import Scheduler

class System:
    '''
    Manufacturing system class
    '''
    def __init__(self,
                 process_times,
                 initial_remaining_process=None,
                 interarrival_time=1, # int
                 buffer_sizes=1, # list or int
                 initial_buffer=0,

                 failure_mode=None,
                 failure_params=None,
                 planned_failures=None, # list of (loc, time, duration)
                 initial_health=None, # initial health states of machines

                 maintenance_policy=None, # CM/PM/CBM, str
                 maintenance_params=None, # define policy
                 repair_params=None, # define TTR
                 maintenance_capacity=None,
                 maintenance_costs=None, # dict of cost by job type

                 scheduler=None,
                 
                 allow_new_maintenance=True, # allow creation of new maintenance jobs

                 debug=False):

        # inferred system characteristics
        self.M = len(process_times) # number of machines
        self.bottleneck_process_time = max(process_times)
        self.bottleneck = process_times.index(self.bottleneck_process_time)

        # specified system characteristics
        self.process_times = process_times
        self.initial_remaining_process = initial_remaining_process
        self.interarrival_time = interarrival_time
        if type(buffer_sizes) == int:
            self.buffer_sizes = [buffer_sizes]*(self.M-1)
        else:
            self.buffer_sizes = buffer_sizes

        if type(initial_buffer) == int:
            self.initial_buffer = [initial_buffer]*(self.M-1)
        else:
            self.initial_buffer = initial_buffer

        # if 'buffer levels' in initiate.keys():
        #     self.initial_buffer = initiate['buffer levels']
        # else:
        #     self.initial_buffer = [0] * (self.M-1)

        self.failure_mode = failure_mode
        self.failure_params = failure_params
        if self.failure_mode:
            if self.failure_mode == 'degradation':
                # Markov degradation
                # TODO: finish flexible degradation
                if 'degradation transition' in failure_params.keys():
                    # complete transition matrix is specified
                    if type(failure_params['degradation transition']) == list:
                        # each machine has its own degradation transition matrix
                        self.degradation_transition = failure_params['degradation transition']
                    else:
                        # same transition matrix for each machine
                        self.degradation_transition = failure_params['degradation transition']*self.M

                else:
                    if type(failure_params['degradation rate']) == list:
                        # rate specified for each machine
                        self.degradation_rate = failure_params['degradation rate']
                    else:
                        # same rate for each machine
                        self.degradation_rate = [failure_params['degradation rate']]*self.M

                    if 'failed state' not in failure_params.keys():
                        # default h_max
                        h_max = [10]*self.M
                    elif type(failure_params['failed state']) == int:
                        # single h_max for all machines
                        h_max = [failure_params['failed state']]*self.M
                                        
                    self.degradation_transition = []
                    for i in range(self.M):
                        rate = self.degradation_rate[i]
                        mat = np.zeros((h_max[i]+1, h_max[i]+1))
                        for j in range(h_max[i]+1):
                            if j < h_max[i]:
                                mat[j][j] = 1 - rate
                                mat[j][j+1] = rate
                            else:
                                mat[j][j] = 1
                        self.degradation_transition.append(mat)

                # if type(failure_params) == float:
                #     self.degradation = [failure_params]*self.M
                # elif type(failure_params) == dict:
                #     self.degradation = failure_params['degradation rate']
                #     self.failure_state = failure_params['failed state']
                # else:
                #     self.degradation = failure_params
                #     self.failure_state = 10


            elif self.failure_mode == 'reliability': # TTF distribution
                if len(failure_params) == 1:
                    self.reliability = [failure_params]*self.M
                else:
                    self.reliability = failure_params

        else: # no degradation
            self.failure_mode = None
            self.degradation_transition = [np.zeros((5,5))]*self.M

        if initial_health:
            self.initial_health = initial_health
        else:
            self.initial_health = [0]*self.M

        # if 'machine health' in initiate.keys():
        #     self.initial_health = initiate['machine health']
        # else:
        #     self.initial_health = [0] * self.M

        self.repair_params = repair_params

        #self.failures = failures
        #if degradation:
        #    self.degradation = degradation
        #else:
        #    self.degradation = [0]*len(process_times)

        self.planned_failures = planned_failures
        self.maintenance_policy = maintenance_policy
        self.maintenance_params = maintenance_params
        if maintenance_capacity:
            self.maintenance_capacity = maintenance_capacity
        else:
            # no capacity by default
            self.maintenance_capacity = self.M
        self.maintenance_costs = maintenance_costs

        #self.scheduling = scheduling

        self.debug = debug

        if scheduler:
            self.scheduler = scheduler
        else:
            self.scheduler = Scheduler()

        self.allow_new_maintenance = allow_new_maintenance

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
        self.available_maintenance = self.maintenance_capacity

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
            self.machines += [Machine(self.env, m, process_time, planned_failures_m,
                              self.failure_mode, self.degradation_transition[m], 
                              self.initial_health[m], self, self.allow_new_maintenance)]

            if self.initial_remaining_process:
                self.machines[m].remaining_process_time = self.initial_remaining_process[m]            

        # initialize scheduler object
        self.scheduler.initialize(self, self.env)

        # initialize system data collection
        state_cols = ['time']     # system state data
        prod_cols = ['time']      # production data
        machine_cols = ['time']   # machine status data


        for machine in self.machines:
            state_cols += [machine.name + ' R(t)']
            if machine.m < (self.M - 1):
                state_cols += ['b{} level'.format(machine.m)]

            prod_cols += [machine.name+' production', machine.name+' throughput']

            machine_cols += [machine.name+' functional', 
                             machine.name+' forced idle',
                             machine.name+' health']

        self.state_data = pd.DataFrame(columns=state_cols)
        self.production_data = pd.DataFrame(columns=prod_cols)
        self.machine_data = pd.DataFrame(columns=machine_cols)
        self.queue_data = pd.DataFrame(columns=['time', 'level', 'contents'])
        self.maintenance_data = pd.DataFrame(columns=['time',
                                                      'machine',
                                                      'type',
                                                      'activity',
                                                      'duration'])
        self.data = {'state': self.state_data,
                     'production': self.production_data,
                     'machine': self.machine_data,
                     'queue':self.queue_data,
                     'maintenance': self.maintenance_data}

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
            np.random.seed(seed)
            random.seed(seed)
            np.random.seed(seed)

        self.initialize() # reinitialize system

        for key in self.data.keys():
            self.data[key]['time'] = list(range(-self.warmup_time, self.sim_time))

        # run simulation
        self.env.run(until=warmup_time+sim_time+1)

        # clean data frames
        #   state data
        for m in range(self.M):
            # clean buffer level data
            if m < self.M-1:
                self.state_data['b{} level'.format(m)].ffill(inplace=True)
                self.state_data['b{} level'.format(m)].fillna(0, inplace=True)                                

            # clean remaining processing time data
            self.state_data['M{} R(t)'.format(m)].fillna(0, inplace=True)

        #  production data
        self.production_data.fillna(method='ffill', inplace=True)
        self.production_data.fillna(0, inplace=True)
        for m in range(self.M):
            TH_col = 'M{} throughput'.format(m)
            self.production_data[TH_col] = self.production_data['M{} production'.format(m)]/self.production_data['time']

        #  machine data
        for m in range(self.M):
            self.machine_data['M{} health'.format(m)].ffill(inplace=True)
            self.machine_data['M{} health'.format(m)].fillna(self.initial_health[m], inplace=True)

            col1 = 'M{} functional'.format(m)
            self.machine_data[col1] = self.machine_data[col1].fillna(1)

            col2 = 'M{} forced idle'.format(m)
            self.machine_data[col2] = self.machine_data[col2].fillna(1)

            self.machines[m].total_downtime = sum(self.machine_data[col2])

            self.machine_data['M{} health'.format(m)].astype(int)

        #  queue data
        self.queue_data.ffill(inplace=True)
        self.queue_data['contents'].fillna(str([]), inplace=True)
        self.queue_data['level'].fillna(0, inplace=True)

        #  maintenance data
        self.maintenance_data.dropna(subset=['machine'], inplace=True)
        self.maintenance_data.reset_index(inplace=True, drop=True)

        if verbose:
            print('Simulation complete in {:.2f}s\n'.format(time.time()-start_time))
            print('  Units produced:      {}'.format(self.machines[-1].parts_made))
            
            functional = ['M{} functional'.format(m) for m in range(self.M)]
            functional = self.machine_data[self.machine_data['time'] >= 0][functional]
            avail = functional.sum().sum() / (self.M * self.sim_time)

            print('  System availability: {:.2f}%\n'.format(avail*100))

    def iterate_simulation(self, replications, warmup_time=0, sim_time=100, 
                           objective='production', verbose=True):
        start_time = time.time()                           
        obj = []
        for _ in range(replications):
            self.simulate(warmup_time=warmup_time, sim_time=sim_time, verbose=False)
        
            if objective == 'production':
                production = self.machines[-1].parts_made
                obj.append(production)
            elif objective == 'ppl':
                ppl = self.machines[self.bottleneck].total_downtime / self.machines[self.bottleneck].process_time
                obj.append(ppl)
            elif objective == 'availability':
                functional = ['M{} functional'.format(m) for m in range(self.M)]
                functional = self.machine_data[self.machine_data['time'] >= 0][functional]
                avail = 100*functional.sum().sum() / (self.M * self.sim_time)
                obj.append(avail)

        stop_time = time.time()
        total_time = stop_time - start_time
        
        if verbose:
            units = {'production': 'units',
                     'ppl': 'units lost production',
                     'availability': '% availability'}
                     
            print('{} replications finished in {:.2f}s, {:.2f}s/rep'
                  .format(replications, total_time, total_time/replications))
            print('Average objective: {:.2f} {}'.format(np.mean(obj), units[objective]))
        
        return obj    

    def draw(self):
        '''
        Draw the system diagram. Only tested for jupyter notebooks.
        '''
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

        # orient horizontally
        sys.graph_attr['rankdir'] = 'LR'

        return sys
