import multiprocessing
import random
import time
import warnings

from .simulation import Environment
from .Source import Source
from .Sink import Sink
from .Machine import Machine
from .Buffer import Buffer
from .Repairman import Repairman

class System:
    def __init__(
        self,
        objects=[],
        repairman=Repairman()
    ):
        self.objects = objects
        self.sources = []
        self.machines = []
        self.buffers = []
        self.sinks = []
        for obj in objects:
            if type(obj) == Source:
                self.sources.append(obj)
            elif type(obj) == Machine:
                self.machines.append(obj)
            elif type(obj) == Buffer:
                self.buffers.append(obj)
            elif type(obj) == Sink:
                self.sinks.append(obj)
        self.repairman = repairman

        # put machines at the front as they should be initialized first
        self.objects.sort(key=lambda obj: not isinstance(obj, Machine))
    
    def initialize(self):
        for machine in self.machines:
            machine.remaining_process_time = machine.initial_remaining_process
            machine.parts_made = 0
            machine.health = machine.initial_health

            if len(machine.upstream) > 1 or len(machine.downstream) > 1:
                warnings.warn(
                    'System configuration includes machines with more than one asset '
                    + 'upstream or downstream, which may result in unexepcted behavior. '
                    + 'It is recommended that the system be rearranged such that each '
                    + 'machine gives and takes from only one buffer.'
                )

        for buffer in self.buffers:
            buffer.level = buffer.initial_level
        
        for sink in self.sinks:
            sink.level = sink.initial_level

        self.repairman.utilization = 0

    def simulate(
        self,
        warm_up_time=0,
        simulation_time=0,
        verbose=True,
        trace=False
    ):
        start = time.time()
        for machine in self.machines:
            machine.repairman = self.repairman

        self.env = Environment(trace=trace)
        for obj in self.objects:
            # should initialize machines first
            obj.env = self.env
            obj.initialize()

        self.repairman.env = self.env
        self.repairman.system = self
        self.repairman.utilization = 0

        self.env.warm_up_time = warm_up_time

        self.env.run(until=warm_up_time+simulation_time)

        # clean up data here
        for machine in self.machines:
            if machine.under_repair or machine.failed:
                machine.downtime += (self.env.now - machine.downtime_start)

        stop = time.time()
        if verbose:
            print(f'Simulation finished in {stop-start:.2f}s')
            print(f'Parts produced: {sum([sink.level for sink in self.sinks])}')

    def iterate_simulation(
        self, 
        replications, 
        warm_up_time=0, 
        simulation_time=0,
        objective='production',
        verbose=True,
        jobs=1
    ):
        start = time.time()
        if jobs == 1: # run replications in series
            samples = []
            for i in range(replications):
                seed = int(str(i) + str(time.time()).split('.')[-1])
                random.seed(seed)
                self.simulate(warm_up_time, simulation_time, verbose=False)
                if objective == 'production':
                    samples.append(sum([sink.level for sink in self.sinks]))
                else:
                    raise NotImplementedError(f'Objective {objective} is not implemented')

        else: # run replications in parallel            
            with multiprocessing.Pool(jobs) as p:
                args = [
                    (seed, warm_up_time, simulation_time)
                    for seed in range(replications)
                ]
                samples = p.starmap(self.simulate_in_parallel, args)

        stop = time.time()

        if verbose:
            print(f'Finished {replications} replications in {stop-start:.2f}s')
        
        return samples

    def simulate_in_parallel(self, seed, warm_up_time, simulation_time):
        seed = int(str(seed) + str(time.time()).split('.')[-1])
        random.seed(seed)
        
        self.simulate(warm_up_time, simulation_time, verbose=False)

        availability = [
            (1 - machine.downtime/(warm_up_time+simulation_time)) 
            for machine in self.machines
        ]

        machine_production = [machine.parts_made for machine in self.machines]

        system_production = sum([sink.level for sink in self.sinks])

        return (system_production, machine_production, availability)
