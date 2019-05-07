import random

import simpy

class Scheduler:
    '''
    Maintenance scheduler class.
    '''
    def __init__(self,
                 system,
                 env,
                 policy='fifo'):
        
        self.system = system
        self.policy = policy

        self.env = env

        self.env.process(self.scheduling())

    def choose_next(self, queue):
        '''
        Choose the next machine on which to perform maintenance. Returns the 
        the chosen machine object.
        '''
        for machine in queue:
            pass
        
        return queue[0]

    def scheduling(self):        
        while True:
            yield self.env.timeout(1)

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
                print('scanning queue at t={}'.format(self.env.now))
                if len(queue) == 0:
                    pass
                elif len(queue) == 1: # TODO: generalize maintenance capacity
                    print('M{} alone in queue'.format(queue[0].m))
                    queue[0].assigned_maintenance = True
                else: # len(queue) > 1
                    print('Multiple machines in queue')
                    next_machine = self.choose_next(queue)
                    next_machine.assigned_maintenance = True