import copy
import multiprocessing
import random
import time
import warnings

from .simulation import Environment
from .Source import Source
from .Sink import Sink
from .Machine import Machine
from .Buffer import Buffer
from .Maintainer import Maintainer

class System:
    def __init__(
        self,
        objects=[],
        maintainer=Maintainer()
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
        self.maintainer = maintainer

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

        self.maintainer.utilization = 0

    def simulate(
        self,
        warm_up_time=0,
        simulation_time=0,
        verbose=True,
        trace=False,
        collect_data=True
    ):
        start = time.time()
        for machine in self.machines:
            machine.maintainer = self.maintainer

        self.env = Environment(trace=trace, collect_data=collect_data)
        for obj in self.objects:
            # should initialize machines first
            obj.env = self.env
            obj.initialize()

        self.maintainer.env = self.env
        self.maintainer.system = self
        self.maintainer.utilization = 0

        self.warm_up_time = warm_up_time
        self.simulation_time = simulation_time

        self.env.run(warm_up_time, simulation_time)

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
        store_system_state=False,
        verbose=True,
        jobs=1,
        seedseed=0
    ):
        """Replicate multiple simulation runs for a specified system. Statistics for
        each run will gathered after the "warm_up_time" has elapsed. Currently the
        following statistics are gathered:
        - Machine
            - Production (units)
            - Availability (proportion of time not failed or under maintenance)
        - Sink
            - Level (units): completed parts that have exited the system

        A nested dictionary is returned with "replications" samples of each statistic.
        """
        start = time.time()      
        with multiprocessing.Pool(jobs) as p:
            args = [
                (seed, warm_up_time, simulation_time, store_system_state)
                for seed in range(seedseed, seedseed+replications)
            ]
            samples = p.starmap(self.simulate_in_parallel, args)
        stop = time.time()

        if verbose:
            print(f'Finished {replications} replications in {stop-start:.2f}s')
        
        return samples

    def simulate_in_parallel(
        self, 
        seed, 
        warm_up_time, 
        simulation_time, 
        store_system_state=False
    ):
        random.seed()
        
        self.simulate(
            warm_up_time, 
            simulation_time, 
            verbose=False, 
            collect_data=store_system_state
        )

        availability = [
            (1 - machine.downtime/(warm_up_time+simulation_time)) 
            for machine in self.machines
        ]

        machine_production = [machine.parts_made for machine in self.machines]

        system_production = sum([sink.level for sink in self.sinks])

        if store_system_state:
            system_state = copy.deepcopy(self)
        else:
            system_state = None

        return (
            system_production, 
            machine_production, 
            availability, 
            system_state
        )
