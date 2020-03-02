import time
import warnings

import simpy

from utils import *

class _Machine(simpy.Resource):
    def __init__(
        self, 
        env=None, 
        capacity=1,

        cycle_time=1,

        failed_state=10,
        degradation_rate=0,
        degradation_matrix=None,

        initial_health=0,
        initial_remaining_process=None
    ):
        super().__init__(env, capacity)

        # machine configuration parameters
        self.cycle_time = cycle_time
        
        if (degradation_rate is not None) and (degradation_matrix is not None):
            warnings.warn((
                'Degradation rate and failed state will be overwritten by '
                'specified degradation matrix.'
            ))
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
        self._env = env

        # intialize machine attributes
        self.health = self.initial_health
        self.remaining_process = self.initial_remaining_process

        # initialize performance statistics
        self.parts_made = 0

    def production(self):
        while True:
            try:
                if self.upstream:
                    for obj in self.upstream:
                        pass
            except:
                pass

