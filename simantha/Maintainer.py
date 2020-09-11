import random 

from .simulation import *

class Maintainer:
    # Basic maintainer, follows FIFO by default
    def __init__(self, name='repairman', capacity=float('inf')):
        self.name = name
        self.capacity = capacity

        self.utilization = 0

        self.env = None
        self.system = None

    def initialize(self):
        self.utilization = 0

    def is_available(self):
        return self.utilization < self.capacity

    def inspect(self):
        # if available, check for machines requesting repair
        current_queue = self.get_queue()
        if (not self.is_available()) or (len(current_queue) == 0):
            # No available capacity and/or empty queue
            return
        else:
            machine = self.choose_maintenance_action(current_queue)
            self.utilization += 1
            machine.in_queue = False
            machine.under_repair = True
            source = f'{self.name}.inspect at {self.env.now}'
            self.env.schedule_event(self.env.now, machine, machine.maintain, source)

    def choose_maintenance_action(self, queue):
        # default fifo policy, break ties randomly
        earliest_request = min(m.time_entered_queue for m in queue)
        candidates = [m for m in queue if m.time_entered_queue == earliest_request]
        return random.choice(candidates)

    def get_queue(self):
        return [machine for machine in self.system.machines if machine.in_queue]
