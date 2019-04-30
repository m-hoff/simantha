import random

import simpy

class Scheduler:
    '''
    Maintenance scheduler class.
    '''
    def __init__(self,
                 system,
                 policy='fifo'):
        self.system = system
        self.policy = policy

    def choose_next(self):
        '''
        Choose the next machine on which to perform maintenance. 
        '''
        queue = []              
        for machine in self.system.machines:
            if machine.request_maintenance:
                queue.append(machine)
        
        if len(queue) == 1:
            return queue[0].m
        