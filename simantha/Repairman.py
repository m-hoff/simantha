import copy

import mcts
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
        queue = []
        #print(f't={self.env.now}')
        for machine in self.system.machines:
            #print(f'M{machine.index}', machine.__dict__, '\n\n')
            if (
                (machine.in_queue) 
                and (machine.health > 0)
                #or ((not machine.under_repair) and (machine.get_health(self.env.now) >= machine.maintenance_threshold))
                # TODO: fix this behavior
                # currently machine health data is updated before it is placed 
                # in the queue, so if it fails at the same time as MCTS is 
                # formulated it will not be considered in the schedule, but will
                # still fail
            ):
                queue.append(machine)

        return queue
        

    def schedule_maintenance(self):
        queue = self.get_queue()

        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'Queue at t={self.env.now}: {[(machine.index, machine.get_health(self.env.now)) for machine in queue]}')
        
        if (len(queue) == 0) or (self.utilization == self.capacity):
            self.update_queue_data()
            return
        elif len(queue) == 1:
            if self.system.debug:
                if self.system.mcts_system:
                    print('MCTS: ', end='')
                print(f'Queue length 1, repairman starting maintenance on M{queue[0].index} at t={self.env.now}')
            #self.utilization += 1
            next_machine = queue[0]
            #self.env.process(queue[0].repair())
            #return
        #elif type(self.scheduling_policy) == list:
        #    # schedule according to list, [first, second, third, ...]
        #    if self.system.debug:
        #        if self.system.mcts_system:
        #            print('MCTS: ', end='')
        #        print(f'Repairman\'s current schedule: {self.scheduling_policy}')
        #    for machine in queue:
        #        #try: # TODO: fix this block
        #        if machine.index == self.scheduling_policy[0]:
        #            next_machine = machine
        #            del(self.scheduling_policy[0])
        #            break
        #        #except:
        #        #    print('ERROR HERE')
        #        #    print(f't={self.env.now}', self.scheduling_policy, [m.index for m in queue])
        #        #    print([machine.allow_new_failures for machine in self.system.machines])
        #    #self.env.process(next_machine.repair())
        else: # len(queue) > 1
            next_machine = self.resolve_simultaneous_repairs()
            
        self.utilization += 1
        self.env.process(next_machine.repair())
    

    def resolve_simultaneous_repairs(self):
        queue = self.get_queue()

        # FIFO policy
        next_machine = min(queue, key=lambda m: m.time_entered_queue)
        
        if self.system.debug:
            if self.system.mcts_system:
                print('MCTS: ', end='')
            print(f'Repairman selecting M{next_machine.index} for repair at t={self.env.now}')

        #self.utilization += 1
        #self.env.process(next_machine.repair())
        return next_machine


    def update_queue_data(self):
        queue_length = len(self.get_queue())
        self.queue_data = np.append(
            self.queue_data, [[self.env.now, queue_length]], axis=0
        )
