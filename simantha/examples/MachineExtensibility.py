"""
An example of extensible machine behavior. Random noise is added to machine health index
readings and monitored periodically instead of continuously. 
"""

import random

import numpy as np

from simantha import Source, Machine, Sink, Maintainer, System, simulation, utils

class SensingEvent(simulation.Event):
    # A new event type is used to assign the correct priority to the sensing event. In
    # this case, sensing events are scheduled just after machine degradation events.
    def get_action_priority(self):
        return 5.5

class ConditionMonitoredMachine(Machine):
    def __init__(self, sensing_interval=1, sensor_noise=0, **kwargs):
        self.sensing_interval = sensing_interval
        self.sensor_noise = sensor_noise
        self.sensor_data = {'time': [], 'reading': []}
        
        super().__init__(**kwargs)
    
    def initialize_addon_processes(self):
        self.env.schedule_event(
            time=self.env.now, 
            location=self, 
            action=self.sense, 
            source=f'{self.name} initial addon process',
            event_type=SensingEvent
        )
        
    def repair_addon_processes(self):
        self.env.schedule_event(
            time=self.env.now,
            location=self,
            action=self.sense,
            source=f'{self.name} repair addon process at {self.env.now}',
            event_type=SensingEvent
        )
    
    def sense(self):
        self.sensor_reading = self.health + np.random.normal(0, self.sensor_noise)
        
        self.sensor_data['time'].append(self.env.now)
        self.sensor_data['reading'].append(self.sensor_reading)
        
        self.env.schedule_event(
            time=self.env.now+self.sensing_interval,
            location=self,
            action=self.sense,
            source=f'{self.name} sensing at {self.env.now}',
            event_type=SensingEvent
        )

def main():
    degradation_matrix = utils.generate_degradation_matrix(h_max=10, p=0.1)
    cm_distribution = {'geometric': 0.1}

    source = Source()
    M1 = ConditionMonitoredMachine(
        name='M1',
        cycle_time=2,
        degradation_matrix=degradation_matrix,
        cm_distribution=cm_distribution,
        sensing_interval=2,
        sensor_noise=1
    )
    sink = Sink()

    source.define_routing(downstream=[M1])
    M1.define_routing(upstream=[source], downstream=[sink])
    sink.define_routing(upstream=[M1])

    system = System(objects=[source, M1, sink])

    random.seed(1)
    system.simulate(simulation_time=6*60)

    # Print true health and corresponding sensor reading
    rows = 12
    print('\ntime  health  sensor reading')
    for time, reading in zip(
        M1.sensor_data['time'][:rows], M1.sensor_data['reading'][:rows]
    ):
        timestamp = max([t for t in M1.health_data['time'] if t <= time])
        idx = M1.health_data['time'].index(timestamp)
        health = M1.health_data['health'][idx]
        print(f'{time:<4}  {health:<3}    {reading:>8.4f}')


if __name__ == '__main__':
    main()
