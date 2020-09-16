import bisect
import pickle
import random
import sys
import time

class Environment:
    """The main simulation environment for Simantha. This is designed to be an
    enviroment specifically for use with Simantha objects and is not intended to be a
    general simulation engine. In general, users of Simantha should not need to
    instantiate an Environment object.
    """
    # Tie-breaking priority list for simultaneous events. See Chapter 3 Mathematical 
    # Modeling of Production Systems in Production Systems Engineering by Li and Meerkov
    # for details regarding the assumed behavior of machine/buffer interaction. Events
    # with a smaller priority value are executed earlier.
    # event_priority = [
    #     # Events at the end of the last time step
    #     'generate_arrival',
    #     'request_space',
    #     'put_part',
    #     'restore',

    #     # Events at the start of the current time step
    #     'maintain_planned_failure',
    #     'degrade',
    #     'enter_queue',
    #     'fail',
    #     'inspect',
    #     'maintain',
    #     'request_part',
    #     'get_part',

    #     # Simulation runtime events
    #     'terminate'
    # ]

    # event_priority = {
    #     event: priority for priority, event in enumerate(event_priority)
    # }

    def __init__(self, name='environment', trace=False, collect_data=True):
        self.events = []
        self.name = name
        self.now = 0

        self.terminated = False

        self.trace = trace
        if self.trace:
            self.event_trace = {
                'time': [],
                'location': [],
                'action': [],
                'source': [],
                'priority': [],
                'status': [],
                'index': []
            }

        self.collect_data = collect_data

        # self.execution_profile = {
        #     'step': 0,
        #     'next_event': 0,
        #     'event_execute': 0,
        #     'event_clean': 0
        # }

    def run(self, until):
        """Simulate the system for the specified run time or until no simulation events
        remain. 
        """
        self.now = 0
        self.terminated = False
        self.events.append(Event(until, self, self.terminate))
        self.event_index = 0

        self.events.sort()

        while self.events and not self.terminated:
            self.step()
            self.event_index += 1

        if self.trace:
            self.export_trace()

    def step(self):
        """Find and execute the next earliest simulation event. Simultaneous events are
        executed in order according to their event type priority, then their
        user-assigned priority. If these values are equal then ties are broken randomly. 
        """
        # step_start = time.time()
        # next_event_start = time.time()

        next_event = self.events.pop(0)

        #next_event_stop = time.time()
        #self.execution_profile['next_event'] += (next_event_stop - next_event_start)

        self.now = next_event.time

        #event_execute_start = time.time()

        try:
            if self.trace:
                self.trace_event(next_event)
            next_event.execute()
        except:
            self.export_trace()
            print('Failed event:')
            print(f'  time:     {next_event.time}')
            print(f'  location: {next_event.location.name}')
            print(f'  action:   {next_event.action.__name__}')
            print(f'  priority: {next_event.priority}')
            sys.exit()

        # event_execute_stop = time.time()
        # self.execution_profile['event_execute'] += (event_execute_stop - event_execute_start)

        # event_clean_start = time.time()
        # #self.events = [ev for ev in self.events if not ev.executed]
        # event_clean_stop = time.time()
        # self.execution_profile['event_clean'] += (event_clean_stop - event_clean_start)

        # step_stop = time.time()
        # self.execution_profile['step'] += (step_stop - step_start)

    def schedule_event(self, time, location, action, source='', priority=0):
        new_event = Event(time, location, action, source, priority)
        bisect.insort(self.events, new_event)

    def terminate(self):
        self.terminated = True

    def trace_event(self, event):
        if self.trace:
            self.event_trace['time'].append(self.now)
            self.event_trace['location'].append(event.location.name)
            self.event_trace['action'].append(event.action.__name__)
            self.event_trace['source'].append(event.source)
            self.event_trace['priority'].append(event.priority)
            self.event_trace['status'].append(event.status)
            self.event_trace['index'].append(self.event_index)

    def export_trace(self):
        if self.trace:
            trace_file = open(f'{self.name}_trace.pkl', 'wb')
            pickle.dump(self.event_trace, trace_file)
            trace_file.close()

class Event:
    event_priority = [
        # Events at the end of the last time step
        'generate_arrival',
        'request_space',
        'put_part',
        'restore',

        # Events at the start of the current time step
        'maintain_planned_failure',
        'degrade',
        'enter_queue',
        'fail',
        'inspect',
        'maintain',
        'request_part',
        'get_part',

        # Simulation runtime events
        'terminate'
    ]

    event_priority = {
        event: priority for priority, event in enumerate(event_priority)
    }

    def __init__(self, time, location, action, source='', priority=0, status=''):
        self.time = time
        self.location = location
        self.action = action
        self.source = source
        self.priority = priority
        self.status = status

        self.tiebreak = random.random()

        self.canceled = False
        self.executed = False

    def execute(self):
        if not self.canceled:
            self.action() 
        else:
            self.status = 'canceled'
        self.executed = True

    def __lt__(self, other):
        return (
            self.time, 
            self.event_priority[self.action.__name__], 
            self.priority, 
            self.tiebreak
        ) < (
            other.time, 
            other.event_priority[other.action.__name__], 
            other.priority, 
            other.tiebreak
        )

def rng(dist):
    if 'constant' in dist.keys():
        # return deterministic value
        return dist['constant']
    elif 'uniform' in dist.keys():
        # uniform distribution, specifed as 
        # {'unifom':[a, b]}
        # returns a number between a and b, inclusive
        a, b = dist['uniform']
        return random.randrange(a, b+1)
    else:
        raise NotImplementedError(f'Invalid distribution specified: {dist}')
