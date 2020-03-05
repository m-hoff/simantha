import copy

import numpy as np


class Repairman:
    def __init__(self, env, system, capacity, scheduling_policy):
        self.env = env
        self.system = system
        
        self.capacity = capacity
        self.utilization = 0

        self.scheduling_policy = scheduling_policy   

        # queue data in the form of [time, queue level]
        self.queue_data = np.zeros((0, 2))
    

    def get_queue(self):
        '''
        Returns a list of machines currently awaiting maintenance. 
        '''
        #queue = []
        #for machine in self.system.machines:
        #    if (machine.in_queue) and (machine.health > 0):
        #        queue.append(machine)
        #return queue

        return [m for m in self.system.machines if m.in_queue]
        

    def schedule_maintenance(self):
        '''
        Check if machines are in the queue, choose one for maintenance if so. 
        '''
        queue = self.get_queue()
        
        if (len(queue) == 0) or (self.utilization == self.capacity):
            #self.update_queue_data()
            return
        elif len(queue) == 1:
            next_machine = queue[0]
        else: # len(queue) > 1
            next_machine = self.resolve_simultaneous_repairs(queue)
            
        self.utilization += 1
        print(f'Choosing M{next_machine.index} for repair at t={self.env.now}')
        self.env.process(next_machine.repair())


    def resolve_simultaneous_repairs(self, queue):
        '''
        Choose between several machines in queue. By default, FIFO is used. 
        '''
        # default FIFO policy
        next_machine = min(queue, key=lambda m: m.time_entered_queue)
        return next_machine


    def update_queue_data(self):
        queue_length = len(self.get_queue())
        self.queue_data = np.append(
            self.queue_data, [[self.env.now, queue_length]], axis=0
        )
