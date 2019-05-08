import numpy as np

import simpy

#from .System import System

class Scheduler:
    '''
    Default maintenance scheduler class. Should only take two arguments, the
    system object that it services and the simulation environment.
    '''
    def __init__(self,
                 system=None,
                 env=None):
        
        # self.system = system

        # self.env = env

        # self.env.process(self.scheduling())

        if system:
            self.initialize(system, env)

    def initialize(self, system, env):
        '''
        Initialize scheduler with new system and simulation environment. 
        '''
        self.system = system
        self.env = env

        self.env.process(self.scheduling())

    def choose_next(self, queue):
        '''
        Choose the next machines on which to perform maintenance. Returns the 
        the chosen machine objects which are then flagged by the scheduling 
        method.
        '''
        # MCTS should be solved here

        n_machines_to_schedule = self.system.available_maintenance
        next_machines =[]
        while n_machines_to_schedule:
            next_machine = queue[np.argmin([m.time_entered_queue for m in queue])]
            next_machines.append(next_machine)
            n_machines_to_schedule -= 1

        return next_machines

    def scheduling(self):            
        '''
        Flags machines to receive maintenance when maintenance resources are 
        available.
        '''
        from .System import System

        while True:
            yield self.env.timeout(1)

            # get list of machines awaiting maintenance
            queue = []
            under_repair = 0
            for machine in self.system.machines:
                if machine.request_maintenance:
                    queue.append(machine)
                if machine.under_repair:
                    under_repair += 1

            #print(self.env.now, ['M{}'.format(mach.m) for mach in queue])
            # scan queue if maintenance resources are available
            if self.system.available_maintenance:
                #print('scanning queue at t={}'.format(self.env.now))
                if len(queue) == 0:
                    pass
                elif len(queue) <= self.system.maintenance_capacity:
                    #print('M{} alone in queue'.format(queue[0].m))
                    for machine in queue:
                        machine.assigned_maintenance = True
                else: # len(queue) > capacity
                    #print('Multiple machines in queue')
                    for machine in self.choose_next(queue):
                        machine.assigned_maintenance = True                