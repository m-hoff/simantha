import time
import random

import numpy as np
import pandas as pd
import simpy

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
        self.n = len(process_times) # number of machines
        self.bottleneck_process_time = max(process_times)
        self.bottleneck = process_times.index(self.bottleneck_process_time)

        # specified system characteristics
        self.process_times = process_times
        self.initial_remaining_process = initial_remaining_process
        self.interarrival_time = interarrival_time
        if type(buffer_sizes) == int:
            self.buffer_sizes = [buffer_sizes]*(self.n-1)
        else:
            self.buffer_sizes = buffer_sizes

        if type(initial_buffer) == int:
            self.initial_buffer = [initial_buffer]*(self.n-1)
        else:
            self.initial_buffer = initial_buffer

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
                        self.degradation_transition = failure_params['degradation transition']*self.n

                else:
                    if type(failure_params['degradation rate']) == list:
                        # rate specified for each machine
                        self.degradation_rate = failure_params['degradation rate']
                    else:
                        # same rate for each machine
                        self.degradation_rate = [failure_params['degradation rate']]*self.n

                    if 'failed state' not in failure_params.keys():
                        # default h_max
                        h_max = [10]*self.n
                    elif type(failure_params['failed state']) == int:
                        # single h_max for all machines
                        h_max = [failure_params['failed state']]*self.n
                                        
                    self.degradation_transition = []
                    for i in range(self.n):
                        rate = self.degradation_rate[i]
                        mat = np.zeros((h_max[i]+1, h_max[i]+1))
                        for j in range(h_max[i]+1):
                            if j < h_max[i]:
                                mat[j][j] = 1 - rate
                                mat[j][j+1] = rate
                            else:
                                mat[j][j] = 1
                        self.degradation_transition.append(mat)

            elif self.failure_mode == 'reliability': # TTF distribution
                if len(failure_params) == 1:
                    self.reliability = [failure_params]*self.n
                else:
                    self.reliability = failure_params

        else: # no degradation
            self.failure_mode = None
            self.degradation_transition = [np.zeros((5,5))]*self.n

        if initial_health:
            self.initial_health = initial_health
        else:
            self.initial_health = [0]*self.n

        self.repair_params = repair_params

        self.planned_failures = planned_failures
        self.maintenance_policy = maintenance_policy
        self.maintenance_params = maintenance_params
        if maintenance_capacity:
            self.maintenance_capacity = maintenance_capacity
        else:
            # no capacity by default
            self.maintenance_capacity = self.n
        self.maintenance_costs = maintenance_costs

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

        for i in range(self.n):
            # buffer objects
            if i < (self.n - 1):
                self.buffers += [simpy.Container(self.env, capacity=self.buffer_sizes[i], init=self.initial_buffer[i])]

            # planned failures for i
            if self.planned_failures:
                planned_failures_i = [DT for DT in self.planned_failures if DT[0] == i]
            else:
                planned_failures_i = []

            # machine objects
            process_time = self.process_times[i]
            self.machines += [Machine(self.env, i, process_time, planned_failures_i,
                              self.failure_mode, self.degradation_transition[i], 
                              self.initial_health[i], self, self.allow_new_maintenance)]

            if self.initial_remaining_process:
                self.machines[i].remaining_process_time = self.initial_remaining_process[i]            

        # initialize scheduler object
        self.scheduler.initialize(self, self.env)

        # initialize system data collection
        state_cols = ['time']     # system state data
        prod_cols = ['time']      # production data
        machine_cols = ['time']   # machine status data

        for machine in self.machines:
            state_cols += [machine.name + ' R(t)']
            if machine.i < (self.n - 1):
                state_cols += ['b{} level'.format(machine.i)]

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
                     'queue': self.queue_data,
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
        for i in range(self.n):
            # clean buffer level data
            if i < self.n-1:
                self.state_data['b{} level'.format(i)].ffill(inplace=True)
                self.state_data['b{} level'.format(i)].fillna(0, inplace=True)                                

            # clean remaining processing time data
            self.state_data['M{} R(t)'.format(i)].fillna(0, inplace=True)

        #  production data
        self.production_data.fillna(method='ffill', inplace=True)
        self.production_data.fillna(0, inplace=True)
        for i in range(self.n):
            TH_col = 'M{} throughput'.format(i)
            self.production_data[TH_col] = self.production_data['M{} production'.format(i)]/self.production_data['time']

        #  machine data
        for i in range(self.n):
            self.machine_data['M{} health'.format(i)].ffill(inplace=True)
            self.machine_data['M{} health'.format(i)].fillna(self.initial_health[i], inplace=True)

            col1 = 'M{} functional'.format(i)
            self.machine_data[col1] = self.machine_data[col1].fillna(1)

            col2 = 'M{} forced idle'.format(i)
            self.machine_data[col2] = self.machine_data[col2].fillna(1)

            #self.machines[i].total_downtime = sum(self.machine_data[col2])

            self.machine_data['M{} health'.format(i)].astype(int)

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
            
            functional = ['M{} functional'.format(i) for i in range(self.n)]
            functional = self.machine_data[self.machine_data['time'] >= 0][functional]
            avail = functional.sum().sum() / (self.n * self.sim_time)

            print('  System availability: {:.2f}%\n'.format(avail*100))

    def iterate_simulation(self, replications, warmup_time=0, sim_time=100, 
                           objective='production', parallelize=False, verbose=True):
        start_time = time.time()                           
        #obj = []
        if parallelize:
            # run iterations in parallel on multiple cpu cores
            from pathos.multiprocessing import ProcessingPool as Pool
            #cores = multiprocessing.cpu_count()

            def simulate_in_parallel(warmup_time, sim_time):
                return self.iterate_simulation(replications=1, warmup_time=warmup_time, sim_time=sim_time, verbose=0)
                # self.simulate(warmup_time=warmup_time, sim_time=sim_time, verbose=False)
            
                # if objective == 'production':
                #     production = self.machines[-1].parts_made
                #     return production
                # elif objective == 'ppl':
                #     ppl = self.machines[self.bottleneck].total_downtime / self.machines[self.bottleneck].process_time
                #     #littles_law = sim_time / self.bottleneck_process_time 
                #     #ppl2 = littles_law - self.machines[self.bottleneck].parts_made
                #     return ppl
                # elif objective == 'availability':
                #     functional = ['M{} functional'.format(i) for i in range(self.n)]
                #     functional = self.machine_data[self.machine_data['time'] >= 0][functional]
                #     avail = 100*functional.sum().sum() / (self.n * self.sim_time)
                #     return avail

            with Pool(replications) as p:
                p_result = p.map(simulate_in_parallel, 
                                 [(warmup_time, sim_time)]*replications)

            stop_time = time.time()
            total_time = stop_time - start_time
            if verbose:
                units = {'production': 'units',
                        'ppl': 'units lost production',
                        'availability': '% availability'}
                        
                print('{} replications finished in {:.2f}s, {:.2f}s/rep'
                    .format(replications, total_time, total_time/replications))
                #print('Average objective: {:.2f} {}'.format(np.mean(obj), units[objective]))

            return p_result

        else:
            obj = []
            for _ in range(replications):
                self.simulate(warmup_time=warmup_time, sim_time=sim_time, verbose=False)
            
                if objective == 'production':
                    production = self.machines[-1].parts_made
                    obj.append(production)
                elif objective == 'ppl':
                    ppl = self.machines[self.bottleneck].total_downtime / self.machines[self.bottleneck].process_time
                    #littles_law = sim_time / self.bottleneck_process_time 
                    #ppl2 = littles_law - self.machines[self.bottleneck].parts_made
                    obj.append(ppl)
                elif objective == 'availability':
                    functional = ['M{} functional'.format(i) for i in range(self.n)]
                    functional = self.machine_data[self.machine_data['time'] >= 0][functional]
                    avail = 100*functional.sum().sum() / (self.n * self.sim_time)
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

    # def draw(self):
    #     '''
    #     Draw the system diagram. Only tested for jupyter notebooks.
    #     '''
    #     sys = Digraph(comment='System layout')

    #     # create machine node shape
    #     sys.attr('node', shape='rectangle', height='0.5', width='0.75')

    #     # create invisible source node
    #     sys.node('source', '', style='invis', width='0.1')

    #     # create node for each machine
    #     for i in range(self.n):
    #         Mi = 'M{}'.format(i)
    #         sys.node(Mi, Mi)

    #     # create node for each buffer
    #     sys.attr('node', shape='circle', **{'height':'0.1', 'width':'0.1'})
    #     for i in range(self.n-1):
    #         Bi = 'B{}'.format(i)

    #         sys.node(Bi, Bi)

    #     # create invisible sink
    #     sys.node('sink', '', style='invis', width='0.1')

    #     # add edges to adjacent nodes
    #     sys.attr('edge', arrowsize='0.65')
    #     sys.edge('source', 'M0')
    #     if self.n > 1:
    #         for i in range(self.n-1):
    #             sys.edge('M{}'.format(i),'B{}'.format(i))
    #             sys.edge('B{}'.format(i),'M{}'.format(i+1))
    #     sys.edge('M{}'.format(self.n-1),'sink')

    #     # orient horizontally
    #     sys.graph_attr['rankdir'] = 'LR'

    #     return sys
