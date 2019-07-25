import numpy as np
import simpy

class Scheduler:
    '''
    Default maintenance scheduler class. Should only take two arguments, the
    system object that it services and the simulation environment.
    '''
    def __init__(self,
                 system=None,
                 env=None,
                 **kwds):
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
        n_machines_to_schedule = self.system.available_maintenance
        next_machines = []
        while n_machines_to_schedule:
            next_machine = queue[np.argmin([i.time_entered_queue if i.time_entered_queue else self.env.now for i in queue])]
            next_machines.append(next_machine)
            n_machines_to_schedule -= 1

            if self.system.debug:
                print(f'Scheduler interrupting M{next_machine.i} processing at t={self.env.now}')
            next_machine.process.interrupt()

        return next_machines # returns machine that will begin maintenance

    def scheduling(self):
        '''
        Flags machines to receive maintenance when maintenance resources are
        available.
        '''
        while True:
            # get list of machines awaiting maintenance
            queue = []
            under_repair = 0
            for machine in self.system.machines:
                if machine.request_maintenance:
                    queue.append(machine)
                if machine.under_repair:
                    under_repair += 1
            # scan queue if maintenance resources are available
            if self.system.available_maintenance:
                if len(queue) == 0:
                    pass
                elif len(queue) <= self.system.maintenance_capacity:
                    for machine in queue:
                        machine.assigned_maintenance = True
                        if self.system.debug:
                            print(f'Scheduler interrupting M{machine.i} processing at t={self.env.now}')
                        machine.process.interrupt()
                else: # len(queue) > capacity
                    # flag all next machines for maintenance
                    for machine in self.choose_next(queue):
                        machine.assigned_maintenance = True    
            
            yield self.env.timeout(1)            
            