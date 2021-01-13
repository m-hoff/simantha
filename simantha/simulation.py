import bisect
import pickle
import random
import sys
import time
import warnings

class Event:
    action_priority = [
        # Events at the end of the last time step
        'generate_arrival',          # Priority: 0 (highest priority)
        'request_space',             # 1 
        'put_part',                  # 2
        'restore',                   # 3

        # Events at the start of the current time step
        'maintain_planned_failure',  # 4
        'degrade',                   # 5
        'enter_queue',               # 6
        'fail',                      # 7
        'inspect',                   # 8
        'maintain',                  # 9
        'request_part',              # 10
        'get_part',                  # 11

        # Simulation runtime events
        'terminate'                  # 12 (lowest priority)
    ]

    action_priority = {
        action: priority for priority, action in enumerate(action_priority)
    }

    def __init__(self, time, location, action, source='', priority=0, status=''):
        self.time = time
        if type(location) == str:
            self.location = location
        elif location is None:
            self.location = ''
        else:
            self.location = location.name
        self.action = action
        self.source = source
        self.priority = priority
        self.status = status

        self.tiebreak = random.random()

        self.canceled = False
        self.executed = False
    
    def get_action_priority(self):
        if self.action.__name__ in self.action_priority.keys():
            return self.action_priority[self.action.__name__]
        else:
            return float('inf')

    def execute(self):
        if not self.canceled:
            self.action() 
        else:
            self.status = 'canceled'
        self.executed = True

    def __lt__(self, other):
        return (
            self.time, 
            self.get_action_priority(),
            self.priority, 
            self.tiebreak
        ) < (
            other.time, 
            other.get_action_priority(),
            other.priority, 
            other.tiebreak
        )

class Environment:
    """The main simulation environment for Simantha. This is designed to be an
    enviroment specifically for use with Simantha objects and is not intended to be a
    general simulation engine. In general, users of Simantha should not need to
    instantiate an Environment object.
    """
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

    def run(self, warm_up_time=0, simulation_time=0):
        """Simulate the system for the specified run time or until no simulation events
        remain. 
        """
        self.now = 0
        self.warm_up_time = warm_up_time
        self.simulation_time = simulation_time
        self.terminated = False
        self.events.append(Event(warm_up_time+simulation_time, self, self.terminate))
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
        next_event = self.events.pop(0)

        self.now = next_event.time

        try:
            if self.trace:
                self.trace_event(next_event)
            next_event.execute()
        except:
            self.export_trace()
            print('Failed event:')
            print(f'  time:     {next_event.time}')
            print(f'  location: {next_event.location}')
            print(f'  action:   {next_event.action.__name__}')
            print(f'  priority: {next_event.priority}')
            sys.exit()

    def schedule_event(
        self, time, location, action, source='', priority=0, event_type=Event
    ):
        if (type(location) != str) and (location is not None):
            location = location.name
        new_event = Event(time, location, action, source, priority)
        bisect.insort(self.events, new_event)

    def terminate(self):
        self.terminated = True

    def trace_event(self, event):
        if self.trace:
            self.event_trace['time'].append(self.now)
            self.event_trace['location'].append(event.location)
            self.event_trace['action'].append(event.action.__name__)
            self.event_trace['source'].append(event.source)
            self.event_trace['priority'].append(event.priority)
            if event.canceled:
                self.event_trace['status'].append('canceled')
            else:
                self.event_trace['status'].append(event.status)
            self.event_trace['index'].append(self.event_index)

    def export_trace(self):
        if self.trace:
            trace_file = open(f'{self.name}_trace.pkl', 'wb')
            pickle.dump(self.event_trace, trace_file)
            trace_file.close()


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

class Distribution:
    """
    A class for random number generation in Simantha. Several built-in distributions are
    available, but any class that returns a single integer value via a `sample` method
    can be used. The built-in distributions are discrete uniform, specified by passing
    {'uniform': [a, b]} to the distribution object, and geometric, specified via
    {'geometric': p}. Constant integer values are also permitted. 
    """
    def __init__(self, distribution):
        if type(distribution) == int:
            self.distribution_type = 'constant'
            self.distribution_parameters = distribution
        elif type(distribution) != dict:
            raise ValueError(
        f'Invalid distribution {distribution}. Distribution should be a dictionary'
        )
        elif len(distribution) > 1:
            raise ValueError(
        f'Invalid distribution {distribution}. Too many dictionary members'
        )
        else:
            for distribution_type, distribution_parameters in distribution.items():
                self.distribution_type = distribution_type
                self.distribution_parameters = distribution_parameters

        if self.distribution_type == 'constant':
            self.mean = self.distribution_parameters
        elif self.distribution_type == 'uniform':
            self.mean = sum(self.distribution_parameters) / 2
        elif self.distribution_type == 'geometric':
            self.mean = 1 / self.distribution_parameters
        else:
            self.mean = None

    def sample(self):
        """Returns a single sample from the specified distribution."""
        if self.distribution_type == 'constant':
            return self.distribution_parameters

        elif self.distribution_type == 'uniform':
            a, b = self.distribution_parameters
            return random.randint(a, b)

        elif self.distribution_type == 'geometric':
            # Returns the number of trials needed to achieve a single success, where the
            # probability of success for each trial is p.
            p = self.distribution_parameters
            s = 1
            while random.random() > p:
                s += 1
            return s

class ContinuousDistribution:
    def __init__(self, distribution):
        warnings.warn('Continuous distributions are not thoroughly tested.')
        for distribution_type, distribution_parameters in distribution.items():
            self.distribution_type = distribution_type
            self.distribution_parameters = distribution_parameters
