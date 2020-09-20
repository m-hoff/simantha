import random
import time
import warnings

from .Asset import Asset
from .simulation import *

class Machine(Asset):
    def __init__(
        self,
        name=None,
        cycle_time=1,
        selection_priority=1,

        degradation_matrix=[[1,0],[0,1]], #  by default, never degrade
        cbm_threshold=None,
        planned_failure=None, # an optional planned failure, in the form of (time, duration)

        pm_distribution=5,
        cm_distribution=10,
        
        # initial machine state
        initial_health=0,
        initial_remaining_process=None
    ):
        # user-specified parameters
        self.name = name
        
        self.cycle_time = Distribution(cycle_time)
        
        #self.cycle_time = cycle_time
        if initial_remaining_process is not None:
            self.initial_remaining_process = initial_remaining_process
        else:
            self.initial_remaining_process = self.get_cycle_time()
            #self.initial_remaining_process = cycle_time
        self.remaining_process_time = self.initial_remaining_process
        self.selection_priority = selection_priority
        
        # initial machine state
        self.has_finished_part = False
        self.initial_health = initial_health
        self.health = initial_health
        self.degradation_matrix = degradation_matrix
        self.failed_health = len(degradation_matrix) - 1
        self.cbm_threshold = cbm_threshold or self.failed_health # if not specified, CM is used
        if self.health == self.failed_health:
            self.failed = True
        else:
            self.failed = False
        self.assigned_maintenance = False
        self.maintainer = None
        self.has_reserved_part = False

        self.pm_distribution = pm_distribution
        self.cm_distribution = cm_distribution

        self.planned_failure = planned_failure

        # check if planned failures and degradation are specified (may cause errors)
        if planned_failure is not None and degradation_matrix[0][0] != 1:
            warnings.warn(
                'Specifying planned failures along with degradtion is untested and may cause errors.'
            )
        
        # routing
        self.upstream = []
        self.downstream = []
        
        # machine status
        self.has_part = False
        self.under_repair = False
        self.in_queue = False
        self.remaining_ttr = None
    
        # machine statistics
        self.parts_made = 0
        self.downtime = 0

        # simulation data
        self.production_data = {'time': [0], 'production': [0]}
        self.health_data = {'time': [0], 'health': [self.health]}
        self.maintenance_data = {'time': [], 'event': []}
        
        self.env = None

        # self.execution_profile = {
        #     'get_part': [],
        #     'request_space': [],
        #     'put_part': [],
        #     'request_part': [],
        #     'degrade': [],
        #     'enter_queue': [],
        #     'fail': [],
        #     'get_time_to_degrade': [],
        #     'maintain': [],
        #     'restore': []
        # }

    def initialize(self):
        self.remaining_process_time = self.initial_remaining_process
        self.health = self.initial_health
        if self.health == self.failed_health:
            self.failed = True
        else:
            self.failed = False
        self.time_entered_queue = -1

        self.has_part = False
        self.under_repair = False
        self.in_queue = False
        self.remaining_ttr = None

        self.target_giver = None
        self.target_receiver = None

        self.blocked = False
        self.starved = True
        
        # initialize statistics
        self.parts_made = 0
        self.downtime = 0

        # schedule planned failures
        if self.planned_failure is not None:
            self.env.schedule_event(
                self.planned_failure[0], self, self.maintain_planned_failure
            )

        # initialize data
        if self.env.collect_data:
            self.production_data = {'time': [0], 'production': [0]}
            self.health_data = {'time': [0], 'health': [self.health]}
            self.maintenance_data = {'time': [], 'event': []}

        # schedule initial events
        time_to_degrade = self.get_time_to_degrade()
        self.env.schedule_event(
            time_to_degrade, self, self.degrade, f'{self.name}.initialize'
        )

    def get_part(self):
        #get_part_start = time.time()
        # Choose a random upstream container from which to take a part.
        #candidate_givers = self.get_candidate_givers(only_free=True)
        assert self.target_giver is not None, f'No giver identified for {self.name}'
        #giver = random.choice(candidate_givers)
        self.target_giver.get(1)

        self.has_part = True

        self.env.schedule_event(
            self.env.now+self.get_cycle_time(),
            #self.env.now+self.cycle_time, 
            self, 
            self.request_space, 
            f'{self.name}.get_part'
        )

        # check if this event unblocked another machine
        for asset in self.target_giver.upstream:
            if asset.can_give() and self.target_giver.can_receive():
                source = f'{self.name}.get_part at {self.env.now}'
                self.env.schedule_event(
                    self.env.now, asset, asset.request_space, source
                )

        self.target_giver = None

        # get_part_stop = time.time()
        # self.execution_profile['get_part'].append(get_part_stop-get_part_start)

    def request_space(self):
        #request_space_start = time.time()
        self.has_finished_part = True
        candidate_receivers = [obj for obj in self.downstream if obj.can_receive()]
        if len(candidate_receivers) > 0:
            self.target_receiver = random.choice(candidate_receivers)
            self.target_receiver.reserve_vacancy(1)
            source = f'{self.name}.request_space at {self.env.now}'
            self.env.schedule_event(self.env.now, self, self.put_part, source)
        else:
            self.blocked = True

        #request_space_stop = time.time()
        #self.execution_profile['request_space'].append(request_space_stop-request_space_start)
            
    def put_part(self):
        #put_part_start = time.time()        
        assert self.target_receiver is not None, f'No receiver identified for {self.name}'

        self.target_receiver.put(1)

        self.parts_made += 1
        self.has_finished_part = False
        self.has_part = False

        if self.env.collect_data:
            self.production_data['time'].append(self.env.now)
            self.production_data['production'].append(self.parts_made)        

        source = f'{self.name}.put_part at {self.env.now}'
        self.env.schedule_event(self.env.now, self, self.request_part, source)

        # check if this event fed another machine
        for asset in self.target_receiver.downstream:
            if self.target_receiver.can_give() and asset.can_receive() and not asset.has_content_request():
                source = f'{self.name}.put_part at {self.env.now}'
                self.env.schedule_event(self.env.now, asset, asset.request_part, source)
        
        self.target_receiver = None

        # put_part_stop = time.time()
        # self.execution_profile['put_part'].append(put_part_stop-put_part_start)

    def request_part(self):
        #request_part_start = time.time()
        candidate_givers = [obj for obj in self.upstream if obj.can_give()]
        if len(candidate_givers) > 0:
            self.starved = False
            self.target_giver = random.choice(candidate_givers)
            self.target_giver.reserve_content(1)
            source = f'{self.name}.request_part at {self.env.now}'
            self.env.schedule_event(self.env.now, self, self.get_part, source)
        else:
            self.starved = True

        #request_part_stop = time.time()
        #self.execution_profile['request_part'].append(request_part_stop-request_part_start)

    def degrade(self):
        #degrade_start = time.time()
        source = f'{self.name}.degrade at {self.env.now}'
        self.health += 1

        if self.env.collect_data:
            self.health_data['time'].append(self.env.now)
            self.health_data['health'].append(self.health)

        time_to_degrade = self.get_time_to_degrade()
        if self.health == self.failed_health:
            self.env.schedule_event(self.env.now, self, self.fail, source)
        elif self.health == self.cbm_threshold:
            self.env.schedule_event(self.env.now, self, self.enter_queue, source)
            self.env.schedule_event(
                self.env.now+time_to_degrade, self, self.degrade, source
            )
        else:
            self.env.schedule_event(
                self.env.now+time_to_degrade, self, self.degrade, source
            )
        
        #degrade_stop = time.time()
        #self.execution_profile['degrade'].append(degrade_stop-degrade_start)

    def enter_queue(self):
        #enter_queue_start = time.time()
        if not self.in_queue:
            if self.env.collect_data:
                self.maintenance_data['time'].append(self.env.now)
                self.maintenance_data['event'].append('enter queue')

            self.time_entered_queue = self.env.now
            self.in_queue = True

        if not self.failed and self.maintainer.is_available():
            source = f'{self.name}.enter_queue at {self.env.now}'
            self.env.schedule_event(
                self.env.now, self.maintainer, self.maintainer.inspect, source
            )
        #enter_queue_stop = time.time()
        #self.execution_profile['enter_queue'].append(enter_queue_stop-enter_queue_start)

    def fail(self):
        #fail_start = time.time()
        self.failed = True
        self.downtime_start = self.env.now

        if not self.in_queue:
            self.enter_queue()

        if self.env.collect_data:
            self.maintenance_data['time'].append(self.env.now)
            self.maintenance_data['event'].append('failure')

        self.cancel_all_events()

        if self.maintainer.is_available():
            source = f'{self.name}.fail at {self.env.now}'
            self.env.schedule_event(
                self.env.now, self.maintainer, self.maintainer.inspect, source
            )
        
        #fail_stop = time.time()
        #self.execution_profile['fail'].append(fail_stop-fail_start)

    def get_cycle_time(self):
        return self.cycle_time.sample()

    def get_time_to_degrade(self):
        #ttd_start = time.time()
        if 1 in self.degradation_matrix[self.health]:
            #ttd_stop = time.time()
            #self.execution_profile['get_time_to_degrade'].append(ttd_stop-ttd_start)
            return float('inf')

        ttd = 0
        next_health = self.health
        while next_health == self.health:
            ttd += 1
            next_health = random.choices(
                population=range(self.failed_health+1),
                weights=self.degradation_matrix[self.health],
                k=1
            )[0]
        #ttd_stop = time.time()
        #self.execution_profile['get_time_to_degrade'].append(ttd_stop-ttd_start)
        return ttd
    
    def maintain(self):
        #maintain_start = time.time()
        if not self.failed:
            self.downtime_start = self.env.now
        self.has_finished_part = False
        self.under_repair = True

        if self.env.collect_data:
            self.maintenance_data['time'].append(self.env.now)
            self.maintenance_data['event'].append('begin maintenance')
        
        self.in_queue = False 
        time_to_repair = self.get_time_to_repair()
        
        self.cancel_all_events()
        
        source = f'{self.name}.maintain at {self.env.now}'
        self.env.schedule_event(self.env.now+time_to_repair, self, self.restore, source)
        #maintain_stop = time.time()
        #self.execution_profile['maintain'].append(maintain_stop-maintain_start)

    def maintain_planned_failure(self):
        self.failed = True
        self.downtime_start = self.env.now
        self.under_repair = True

        if self.env.collect_data:
            self.maintenance_data['time'].append(self.env.now)
            self.maintenance_data['event'].append('planned failure')
        
        self.cancel_all_events()
        
        time_to_repair = self.planned_failure[1]
        source = f'{self.name}.maintain_planned_failure at {self.env.now}'
        self.env.schedule_event(
            self.env.now+time_to_repair, self, self.restore, source
        )

    def restore(self):
        #restore_start = time.time()
        self.health = 0
        self.under_repair = False
        self.failed = False
        
        self.maintainer.utilization -= 1

        self.downtime += (self.env.now - self.downtime_start)

        if self.env.collect_data:
            self.maintenance_data['time'].append(self.env.now)
            self.maintenance_data['event'].append('repaired')

            self.health_data['time'].append(self.env.now)
            self.health_data['health'].append(self.health)  

        source = f'{self.name}.restore at {self.env.now}'
        self.env.schedule_event(self.env.now, self, self.request_part, source)
        time_to_degrade = self.get_time_to_degrade()
        self.env.schedule_event(
            self.env.now+time_to_degrade, self, self.degrade, source
        )
        
        # repairman to scan queue once released
        self.env.schedule_event(
            self.env.now, self.maintainer, self.maintainer.inspect, source
        )
        #restore_stop = time.time()
        #self.execution_profile['restore'].append(restore_stop-restore_start)
    
    def requesting_maintenance(self):
        return (
            (not self.under_repair)
            and ((self.failed) or (self.health >= self.cbm_threshold))
            and (not self.assigned_maintenance)
        )
        
    def get_time_to_repair(self):
        if self.failed:
            return rng(self.cm_distribution)
        else:
            return rng(self.pm_distribution)
        
    def define_routing(self, upstream=[], downstream=[]):
        self.upstream = upstream
        self.downstream = downstream

    def can_receive(self):
        return (
            (not self.under_repair)
            and (not self.failed)
            and (not self.has_part)
        )

    def can_give(self):
        return (
            (self.has_finished_part)
            and (not self.under_repair)
            and (not self.failed)
        ) or (
            (self.has_finished_part)
            and (self.downtime_start == self.env.now)
        )

    def has_content_request(self):
        # check if a machine has an existing request for a part
        for event in self.env.events:
            if (
                ((event.location is self) and (event.action.__name__ == 'request_part'))
                or ((event.location is self) and (event.action.__name__ == 'get_part'))
            ):
                return True
        return False

    def has_vacancy_request(self):
        for event in self.env.events:
            if (event.location is self) and (event.action.__name__ == 'request_space'):
                return True
        return False

    def cancel_all_events(self):
        # cancel all events scheduled on this machine
        for event in self.env.events:
            if event.location == self:
                event.canceled = True

    def get_candidate_givers(self, only_free=False, blocked=False):
        if blocked:
            # get only candidate givers that can give a part
            return [obj for obj in self.get_candidate_givers() if obj.blocked]
        else:
            return [obj for obj in self.upstream if obj.can_give()]

    def get_candidate_receivers(self, only_free=False, starved=False):
        if starved:
            return [obj for obj in self.get_candidate_receivers() if obj.starved]
        else:
            # get only candidate receivers that can accept a part
            return [obj for obj in self.downstream if obj.can_receive()]
