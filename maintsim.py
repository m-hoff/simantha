import sys
import simpy
import numpy as np
import pandas as pd
#import matplotlib.pyplot as plt
#import matplotlib.patches as mpatches
import math
import random
from scipy.stats import randint
from scipy.stats import geom
from scipy.stats import binom
import time
import datetime

'''
Simulation parameters
'''
class SimulationParameters:
    def __init__(self,
                process_times,
                sim_time,

                sim_title='Simulation',

                interarrival_time=1,
                buffer_sizes=False,

                # TODO: degradation should be P(degrade), not 1-P(degrade)
                degradation=False,

                maint_policy='CM',
                repair_dist=False,
                repair_params='none',
                queue_discipline='fifo',
                maint_capacity=1,
                pm_interval=0,
                pm_duration=0,

                cm_cost=0,
                pm_cost=0,
                lp_cost=0,
                prod_req=0,

                warmup_time=0,

                random_seed='none',

                verbose=True):

        self.SIM_TITLE = sim_title # title for filename(s)

        # system configuration parameters
        self.PROCESS_TIMES = process_times
        self.NUM_MACHINES = len(process_times)
        self.INTERARRIVAL_TIME = interarrival_time

        # TODO: buffer size = 0 => no buffer (?)
        if buffer_sizes:
            if type(buffer_sizes) is list:
                self.BUFFER_SIZES = buffer_sizes
            # if buffers are sparse, they can be passed as a dict in the form
            # of {machine number:buffer size}
            elif type(buffer_sizes) is dict:
                self.BUFFER_SIZES = [1] * self.NUM_MACHINES
                for b in buffer_sizes.keys():
                    self.BUFFER_SIZES[b] = buffer_sizes[b]
        else:
            self.BUFFER_SIZES = [1] * self.NUM_MACHINES

        #print(self.BUFFER_SIZES)

        if degradation:
            self.DEGRADATION = degradation
        else:
            self.DEGRADATION = [1] * self.NUM_MACHINES

        # maintenance policy parameters
        self.MAINT_POLICY = maint_policy # 'CM', 'PM', 'CBM'

        # distribution of repair times
        self.REPAIR_DIST = repair_dist
        '''
        repair_dist should be either uniform, geometric, or binomial (discrete
        distributions from scipy.stats). TODO: validate input as one of these
        options, validate parameter input
        '''
        if repair_dist:
            if repair_dist == 'uniform':
                self.REPAIR_DIST = randint.rvs
            elif repair_dist == 'geometric':
                self.REPAIR_DIST = geom.rvs
            elif repair_dist == 'binomial':
                self.REPAIR_DIST = binom.rvs
            else:
                self.REPAIR_DIST = randint.rvs
                # default repair_dist should be ttr=1 (constant)
                self.REPAIR_PARAMS = (1,1)
        self.REPAIR_PARAMS = repair_params

        self.QUEUE_DISCIPLINE = queue_discipline # 'fifo' or 'priority'
        self.MAINT_CAPACITY = maint_capacity

        # how to handle scheduled PM jobs?
        self.PM_INTERVAL = pm_interval # time between PM activities
        self.PM_DURATION = pm_duration # duration of PM

        # cost data
        self.CM_COST = cm_cost # cost of a corrective maintenance action
        self.PM_COST = pm_cost # cost of a preventative maintenance action
        self.LP_COST = lp_cost # cost of lost production (per unit)
        self.PROD_REQ = prod_req

        # simulation parameters
        self.RANDOM_SEED = random_seed # set to 'none' if no seed is to be used
        self.WARMUP_TIME = warmup_time
        self.SIM_TIME = sim_time

        # run options
        self.VERBOSE = verbose
        #self.PLOT = plots
        #self.SAVE = save_result

    # machine processing
    #def pt(self):
    #    return random.randint(self.MIN_PT, self.MAX_PT)

    # machine time to failure
    def ttf(self):
        if self.MAINT_POLICY == 'CM':
            #return round(random.expovariate(1/self.MTTF))
            return round(112*np.random.weibull(3))
        elif self.MAINT_POLICY == 'PM':
            return round(112*np.random.weibull(3))

    # machine time to repair
    def ttr(self):
        #return round(random.randint(self.MIN_REPAIR, self.MAX_REPAIR))
        return self.REPAIR_DIST(*repair_params)

'''
Machine object
'''
class Machine():
    # env, i, p.PROCESS_TIMES[i], rand_failures=True, repairman
    def __init__(self, env, idx, process_time, rand_failures, repairman, scenario):
        self.scenario = scenario
        self.p = self.scenario.p
        self.buffers = scenario.buffers

        self.env = env
        self.idx = idx
        if scenario.p.MAINT_POLICY == 'CBM':
            self.threshold = scenario.thresholds[self.idx]
        else:
            self.threshold = 99999
        self.process_time = process_time

        self.rand_failures = rand_failures
        self.broken = False
        self.total_failure = False
        self.repair_type = 'none'

        self.parts_made = 0

        self.health = 0
        #self.maintenance_threshold = 6 # state at which to schedule maintenance

        #self.scenario.production_data.loc[:, 'M{} running'.format(self.idx)] = 1

        # assign input buffer
        self.in_buff = eval('self.buffers[{}].buffer'.format(idx))

        # assign output buffer (except last station)
        if self.idx + 1 < self.p.NUM_MACHINES:
            self.out_buff = eval('self.buffers[{}].buffer'.format(idx+1))

        self.process = self.env.process(self.working(repairman))
        self.env.process(self.deteriorate())

    def working(self, repairman):
        prev_part = 0
        while True:
            try:
                # retrieve part from input buffer (except for first machine in line)
                if self.idx > 0:
                    yield self.in_buff.get(1)

                # process part
                yield self.env.timeout(self.process_time)

                # put processed part in output buffer (except last machine in line)
                if self.idx + 1 < self.p.NUM_MACHINES:
                    yield self.out_buff.put(1)

                if (self.env.now > self.p.WARMUP_TIME) and (not self.total_failure):
                    self.parts_made += 1
                    self.scenario.production_data.loc[prev_part-self.p.WARMUP_TIME:self.env.now-self.p.WARMUP_TIME,
                           'Machine {} production'.format(self.idx)] = self.parts_made - 1
                    prev_part = self.env.now

            except simpy.Interrupt: # processing is interrupted if a failure occurs
                #global maintenance_df
                #global repairs
                self.broken = True
                #print('Machine {} broken down at t = {}'.format(self.idx, self.env.now-self.p.WARMUP_TIME))
                #print('Job priority: {}\n'.format(self.priority))

                # TODO: correct TTR distributions
                if (self.health < 10) and (self.p.MAINT_POLICY=='CBM'): # preventive repair
                    time_to_repair = random.randint(5, 15)
                else: # total failure
                    time_to_repair = random.randint(10, 20)
                #time_to_repair = self.p.REPAIR_DIST()
                #time_to_repair = random.randint(5, 15)#self.p.REPAIR_DIST(5, 15)

                # request repairman resource
                with repairman.request(priority=self.get_priority()) as req:
                    yield req
                    #print('Mahcine {} repair started at {}'.format(self.idx, self.env.now))
                    fail_start = self.env.now # start time of repair job
                    # write type of job started
                    if self.total_failure:
                        job_type = 'CM'
                    else:
                        job_type = 'CBM'

                    # add entry to maintenance dataframe for repair start
                    q_time = fail_start - self.enter_q
                    repair_start = pd.DataFrame([[self.env.now-self.p.WARMUP_TIME, int(self.idx), job_type, 'repair start', q_time]],
                                                columns=['time', 'machine', 'type', 'activity', 'TTF/TTR'])
                    self.scenario.maintenance_data = self.scenario.maintenance_data.append(repair_start, ignore_index=True)

                    # repair start 'TTF/TTR' = queue time

                    yield self.env.timeout(time_to_repair)
                    #print('Machine {} repair ended at {}'.format(self.idx, self.env.now))
                self.health = 0
                self.broken = False
                #repairs += [(self.idx, fail_start, self.env.now)]

                #yield self.env.timeout(time_to_repair)
                self.scenario.production_data.loc[fail_start-self.p.WARMUP_TIME:self.env.now-self.p.WARMUP_TIME-1,
                                                    'M{} running'.format(self.idx)] = 0
                #print('Machine {} repaired at t = {}'.format(self.idx, self.env.now-self.p.WARMUP_TIME))

                maint_start = fail_start-self.p.WARMUP_TIME
                maint_end = self.env.now-self.p.WARMUP_TIME

                self.scenario.production_data.loc[maint_start:maint_end, 'M{} running'.format(self.idx)] = 0

                # add entry to maintenance dataframe for repair end
                if self.total_failure:
                    # corrective maintenance activity was performed
                    new_maint = pd.DataFrame([[self.env.now-self.p.WARMUP_TIME, int(self.idx), 'CM', 'repair end', time_to_repair]],
                                            columns=['time', 'machine', 'type', 'activity', 'TTF/TTR'])
                else:
                    # CBM activity was performed
                    new_maint = pd.DataFrame([[self.env.now-self.p.WARMUP_TIME, int(self.idx), 'CBM', 'repair end', time_to_repair]],
                                            columns=['time', 'machine', 'type', 'activity', 'TTF/TTR'])

                self.scenario.maintenance_data = self.scenario.maintenance_data.append(new_maint, ignore_index=True)

                self.broken = False
                self.total_failure = False
                #print('Job finished at time {} and health index {}'.format(self.env.now, self.health))

    # health index deterioration process
    def deteriorate(self):
        while True:
            while (random.random() < self.p.DEGRADATION[self.idx]):
                yield self.env.timeout(1)
                #health[self.idx] += [self.health]
            yield self.env.timeout(1)
            if len(self.scenario.maintenance_data[self.scenario.maintenance_data['machine']==self.idx]['time']) > 0:
                #last_failure_time = 0
                last_failure_time = list(self.scenario.maintenance_data[self.scenario.maintenance_data['machine']==self.idx]['time'])[-1]
            else:
                last_failure_time = -self.p.WARMUP_TIME
            if self.health < 10:
                self.health += 1
                if self.health == 10:
                    if self.p.MAINT_POLICY == 'CM':
                        self.enter_q = self.env.now
                        #print('Machine {} entered Q at {}'.format(self.idx, self.enter_q))
                    self.total_failure = True
                    new_maint = pd.DataFrame([[self.env.now-self.p.WARMUP_TIME, self.idx, 'CM', 'failure', self.env.now-self.p.WARMUP_TIME-last_failure_time]],
                                            columns=['time','machine','type','activity','TTF/TTR'])
                    self.repair_type = 'CM'
                    self.scenario.maintenance_data = self.scenario.maintenance_data.append(new_maint, ignore_index=True)
                    self.process.interrupt()

            if (self.p.MAINT_POLICY == 'CBM') & (self.health == self.threshold):
                self.enter_q = self.env.now
                new_maint = pd.DataFrame([[self.env.now-self.p.WARMUP_TIME, self.idx, 'CBM', 'scheduled', self.env.now]],
                                         columns=['time','machine','type','activity','TTF/TTR'])
                self.scenario.maintenance_data = self.scenario.maintenance_data.append(new_maint, ignore_index=True)

                self.process.interrupt()

    def get_priority(self):
            # calculate maintenance opportunity window at time of maintenance scheduling
            # determine position in relation to bottleneck
            # find contents of upstream/downstream buffers
            # calculate maintenance window
            if self.p.QUEUE_DISCIPLINE == 'priority':
                # upstream of bottleneck
                # W = bottleneck time * sum(buffer contents between machine and bottleneck)
                if self.idx < self.scenario.bottleneck:
                    #print('upstream of bottleneck')
                    buffer_contents = 0
                    for b in range(self.idx+1, self.scenario.bottleneck+1):
                        #print('buffer {} contents: {}'.format(b, self.scenario.buffers[b].buffer.level))
                        buffer_contents += self.scenario.buffers[b].buffer.level
                    W = max(self.p.PROCESS_TIMES) * buffer_contents
                # bottleneck
                elif self.idx == self.scenario.bottleneck:
                    #print('at bottleneck')
                    W = 0
                # downstream of bottleneck
                # IGNORE FIRST INPUT BUFFER
                # W = bottleneck time * sum(buffer cap - buffer contents for buffer between bottleneck and machine)
                else:
                    buffer_contents = 0
                    #print('downstrem of bottleneck')
                    for b in range(self.scenario.bottleneck+1, self.idx+1):
                        #print('buffer {} contents: {}'.format(b, self.scenario.buffers[b].buffer.level))
                        buffer_contents += (self.p.BUFFER_SIZES - self.scenario.buffers[b].buffer.level)
                    W = max(self.p.PROCESS_TIMES) * buffer_contents
            else:
                W = 1

            return W


# buffer object
class Buffer():
    def __init__(self, env, idx, cap):
        self.env = env
        self.idx = idx
        self.cap = cap
        self.buffer = simpy.Container(env, capacity=cap)

# source object
def source(env, interarrival, scenario):
    yield env.timeout(interarrival)
    yield scenario.buffers[0].buffer.put(1) # a part is put in the first buffer every arrival interval

# maintenance worker other jobs
'''
def other_jobs(env, repairman):
    while True:
        duration = 1 # time between other jobs
        while duration:
            with repairman.request(priority=99999) as req:
                yield req
                try:
                    start = env.now
                    yield env.timeout(duration)
                    duration = 0
                except simpy.Interrupt:
                    duration -= env.now - start
'''

# scenario object for a given set of parameters
class Scenario:
    def __init__(self, parameters, **policy_parameters):
        self.p = parameters

        if self.p.MAINT_POLICY == 'PM':
            # try...except
            self.pm_interval = policy_parameters['interval']
            self.pm_duration = policy_parameters['duration']
        elif self.p.MAINT_POLICY == 'CBM':
            self.thresholds = policy_parameters['thresholds']

        #self.thresholds = thresholds # CBM thresholds
        self.bottleneck = self.p.PROCESS_TIMES.index(max(self.p.PROCESS_TIMES))

    def simulate(self, summary=True, data_collect=True, get_costs=False):
        # initialize simulation environment and objects
        self.env = simpy.Environment()
        self.policy_cost = 0
        self.r_b = max(self.p.PROCESS_TIMES) # bottleneck time

        self.repairman = simpy.PriorityResource(self.env, capacity=self.p.MAINT_CAPACITY)

        # input buffers of each machine
        bs = self.p.BUFFER_SIZES
        self.buffers = [Buffer(self.env, i, bs[i]) for i in range(self.p.NUM_MACHINES)]

        self.machines = [Machine(self.env, i, self.p.PROCESS_TIMES[i], rand_failures=True,
                                 repairman=self.repairman, scenario=self) for i in range(self.p.NUM_MACHINES)]

        # initialize simulation data frames
        # production data frame
        self.production_data = pd.DataFrame(index=list(range(-self.p.WARMUP_TIME, self.p.SIM_TIME, 1)),
                      columns=['Machine {} production'.format(i) for i in range(self.p.NUM_MACHINES)]
                      +['Machine {} TH'.format(j) for j in range(self.p.NUM_MACHINES)]
                      +['M{} running'.format(k) for k in range(self.p.NUM_MACHINES)]
                      +['Ideal production'])

        machines_avail = ['M{} running'.format(m) for m in range(self.p.NUM_MACHINES)]
        self.production_data.loc[:,machines_avail] = 1

        # summary data frame
        self.summary_data = pd.DataFrame(index=['Machine {}'.format(m) for m in range(self.p.NUM_MACHINES)]+['System'],
                             columns=['processing time', 'units produced', 'TH', 'MTTF', 'MTTR', 'availability'])

        # maintenance data frome
        self.maintenance_data = pd.DataFrame(columns=['time', 'machine', 'type', 'activity', 'TTF/TTR'])


        # start timer
        start_time = time.time()

        if self.p.RANDOM_SEED is not 'none':
            random.seed(self.p.RANDOM_SEED)

        '''
        initiate processes and run simulation
        '''
        # initiate repairman
        #self.env.process(other_jobs(self.env, self.repairman))

        # source process
        self.env.process(source(self.env, self.p.INTERARRIVAL_TIME, scenario=self))

        self.env.run(until=self.p.WARMUP_TIME+self.p.SIM_TIME)

        if data_collect:
            # production data
            raw_production = ['Machine {} production'.format(m) for m in range(self.p.NUM_MACHINES)]
            self.production_data.loc[:,'Ideal production'] = self.production_data.index * (1/self.r_b)

            for m in range(self.p.NUM_MACHINES):
                machine_p = 'Machine {} production'.format(m)
                machine_th = 'Machine {} TH'.format(m)
                self.production_data.loc[:,machine_p].fillna(max(self.production_data.loc[:,machine_p])+1, inplace=True)
                self.production_data.loc[:,machine_th] = self.production_data.loc[:,machine_p] / self.production_data.index.values

            # summary data
            for m in range(self.p.NUM_MACHINES):
                machine = 'Machine {}'.format(m)
                self.summary_data.loc[machine, 'processing time'] = self.p.PROCESS_TIMES[m]
                self.summary_data.loc[machine, 'units produced'] = self.production_data[machine+' production'].iloc[-1]
                self.summary_data.loc[machine, 'TH'] = self.production_data[machine+' TH'].iloc[-1]

                #TODO: summarize maintenance
                m_maint = self.maintenance_data[self.maintenance_data['machine'] == m]

                ttfs = m_maint[m_maint['activity'] == 'failure']['TTF/TTR']
                ttrs = m_maint[m_maint['activity'] == 'repair end']['TTF/TTR']

                mttf = np.mean(ttfs)
                mttr = np.mean(ttrs)

                self.summary_data.loc[machine, 'MTTF'] = mttf
                self.summary_data.loc[machine, 'MTTR'] = mttr

                self.summary_data.loc[machine, 'availability'] = sum(self.production_data['M{} running'.format(m)])/self.p.SIM_TIME

            # compile summary statistics
            self.summary_data.loc['System', 'processing time'] = 'bottleneck time = {}'.format(self.r_b)
            u = self.summary_data.loc['Machine {}'.format(self.p.NUM_MACHINES-1), 'units produced']
            self.summary_data.loc['System', 'units produced'] = u
            self.summary_data.loc['System', 'TH'] = u / self.p.SIM_TIME

            # summary maintenance statistics
            # MTTF
            # TODO: how to define TTF? TT(total)F?
            self.summary_data.loc['System', 'MTTF'] = np.mean(self.summary_data['MTTF'][:-1])

            # MTTR
            self.summary_data.loc['System', 'MTTR'] = np.mean(self.summary_data['MTTR'][:-1])

            # availability
            self.summary_data.loc['System', 'availability'] = np.mean(self.summary_data['availability'][:-1])

            # average queue time
            maint = self.maintenance_data
            for m in range(self.p.NUM_MACHINES):

                waits = maint[(maint['machine'] == m)
                            & (maint['activity'] == 'repair start')
                            & (maint['time'] >= 0)]['TTF/TTR']
                avg_q_time = np.mean(waits)

                self.summary_data.loc['Machine {}'.format(m), 'avg queue time'] = avg_q_time

            all_waits = maint[maint['activity'] == 'repair start']['TTF/TTR']
            self.summary_data.loc['System', 'avg queue time'] = np.mean(all_waits)

        # policy cost calculation
        maint = self.maintenance_data[self.maintenance_data['time'] >= 0]

        repairs = maint[maint['activity'] == 'repair end']
        # PM costs
        n_cbm_repairs = len(repairs[repairs['type']=='PM']) + len(repairs[repairs['type']=='CBM'])
        cbm_maintenance_cost = self.p.PM_COST * n_cbm_repairs

        # CM costs
        n_cm_repairs = len(repairs[repairs['type']=='CM'])
        cm_maintenance_cost = self.p.CM_COST * n_cm_repairs

        lost_production_cost = (((self.p.SIM_TIME / self.r_b) - self.machines[-1].parts_made) * self.p.LP_COST)

        self.policy_cost = cbm_maintenance_cost + cm_maintenance_cost + lost_production_cost

        self.cost_data = pd.Series(index=['PM cost', 'CM cost', 'LP cost', 'Total cost'],
                                    data=[cbm_maintenance_cost, cm_maintenance_cost, lost_production_cost, self.policy_cost])

        # TODO: change summary output
        if summary:
            print(self.summary_data)

        if get_costs:
            return cbm_maintenance_cost, cm_maintenance_cost, lost_production_cost, self.policy_cost

    def iterate_simulation(self, iterations, get_runs=False, verbose=False):
        self.runs = [self.simulate(summary=False, data_collect=False, get_costs=True) for i in range(iterations)]

        #self.runs = [Scenario(self.p, self.thresholds) for i in range(iterations)]
        #results = [s.simulate(summary=False) for s in self.runs]

        #average_cost = sum([r.policy_cost for r in self.runs]) / iterations

        if get_runs:
            return [r[3] for r in self.runs]

        pm, cm, lp, tot = 0, 0, 0, 0
        samp = []
        for r in self.runs:
            pm += r[0]
            cm += r[1]
            lp += r[2]
            tot += r[3]
            samp += [r[3]]

        avg_pm = pm / iterations
        avg_cm = cm / iterations
        avg_lp = lp / iterations
        avg_tot = tot / iterations

        #average_cost = sum(self.runs) / iterations

        standard_error = np.std(samp) / (iterations**0.5)

        if verbose:
            print(pd.DataFrame([avg_pm, avg_cm, avg_lp, avg_tot, standard_error],
                        index=['PM', 'CM', 'LP', 'Total', 'SE'],
                        columns=['average cost']))

        else:
            return avg_pm, avg_cm, avg_lp, avg_tot, standard_error

    # evaluate a CBM policy solution
    def evaluate_solution(self, soln, samples=False):
        self.thresholds = soln

        if samples:
            return self.iterate_simulation(20, get_runs=True)

        avg_pm, avg_cm, avg_lp, avg_tot, se = self.iterate_simulation(50)
        return avg_tot, se



# In[4]:

simple_test_case = SimulationParameters(
    process_times = [3, 1, 2],
    sim_time = 100,

    sim_title = 'Simple Test Case',
)
