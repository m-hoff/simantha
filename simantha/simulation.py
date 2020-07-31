import pickle
import random
import sys

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

    def __init__(self, name='environment', trace=False):
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

    def run(self, until):
        """Simulate the system for the specified run time or until no simulation events
        remain. 
        """
        self.now = 0
        self.terminated = False
        self.events.append(Event(until, self, self.terminate))
        self.event_index = 0

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
        next_event = min(
            self.events, 
            key=lambda ev: (
                (
                    ev.time, 
                    self.event_priority[ev.action.__name__], 
                    ev.priority, 
                    random.random()
                )
            )
        )

        self.now = next_event.time

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

        self.events = [ev for ev in self.events if not ev.executed]

    def schedule_event(self, time, location, action, source='', priority=0):
        new_event = Event(time, location, action, source, priority)
        self.events.append(new_event)

    def terminate(self):
        self.events = []
        self.terminated = True
        return

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
    def __init__(self, time, location, action, source='', priority=0, status=''):
        self.time = time
        self.location = location
        self.action = action
        self.source = source
        self.priority = priority
        self.status = status

        self.canceled = False
        self.executed = False

    def execute(self):
        if not self.canceled:
            self.action() 
        else:
            self.status = 'canceled'
        self.executed = True

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
