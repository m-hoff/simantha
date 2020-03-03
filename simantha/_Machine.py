import time
import warnings

import simpy

from utils import *

#class _Machine(simpy.Resource):
class _Machine:
    def __init__(
        self, 
        env=None, 

        cycle_time=1,
        capacity=1,

        failed_state=10,
        degradation_rate=0,
        degradation_matrix=None,

        initial_health=0,
        initial_remaining_process=None
    ):
        #super().__init__(env, capacity)

        # machine configuration parameters
        self.cycle_time = cycle_time
        self.capacity = capacity

        if (degradation_rate is not None) and (degradation_matrix is not None):
            warnings.warn(
                'Degradation rate and failed state will be overwritten by '
                'specified degradation matrix.'
            )
            self.degradation_matrix = degradation_matrix
            self.failed_state = len(degradation_matrix) - 1
        else:
            self.degradation_matrix = create_degradation_matrix(
                failed_state, degradation_rate
            )
            self.failed_state = failed_state

        # initial machine conditions
        self.initial_health = initial_health
        self.initial_remaining_process = initial_remaining_process

    def initialize(self, env):
        self.env = env

        # TODO: verify naming, functionality, etc. 
        self.contents = simpy.Container(env, self.capacity)

        # intialize machine attributes
        self.health = self.initial_health
        self.remaining_process = self.initial_remaining_process

        self.finished_parts = 0
        self.work_in_process = 0

        # initialize performance statistics
        self.parts_made = 0

    def production(self):
        while True:
            try:
                # get part from upstream object
                #TODO: assign priority to upstream objects
                for upstream_object in self.upstream:
                    if upstream_object.contents.level:
                        yield upstream_object.contents.get(1)
                        self.contents.put(1)

                
            except:
                pass
