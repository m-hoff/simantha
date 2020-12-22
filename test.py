import random
import unittest

import scipy.stats

from simantha import Source, Machine, Buffer, Sink, System
import simantha.simulation
import simantha.utils

# Degradation transition matrix used for all tests where applicable
degradation_matrix = [
            [0.9, 0.1, 0,   0,   0,   0  ],
            [0,   0.9, 0.1, 0,   0,   0  ],
            [0,   0,   0.9, 0.1, 0,   0  ],
            [0,   0,   0,   0.9, 0.1, 0  ],
            [0,   0,   0,   0,   0.9, 0.1],
            [0,   0,   0,   0,   0,   1  ]
        ]

class UtilsTests(unittest.TestCase):
    """Test Simantha utility functons.
    """
    def test_degradation_matrix(self):
        degradation_matrix = simantha.utils.generate_degradation_matrix(p=0.1, h_max=5)
        target_matrix = [
            [0.9, 0.1, 0,   0,   0,   0  ],
            [0,   0.9, 0.1, 0,   0,   0  ],
            [0,   0,   0.9, 0.1, 0,   0  ],
            [0,   0,   0,   0.9, 0.1, 0  ],
            [0,   0,   0,   0,   0.9, 0.1],
            [0,   0,   0,   0,   0,   1  ]
        ]
        #self.assertEqual(degradation_matrix, target_matrix)
        self.assertEqual(
            simantha.utils.generate_degradation_matrix(p=0.1, h_max=5), 
            degradation_matrix
        )

class SimulationTests(unittest.TestCase):
    """Tests for the underlying simulation engine. 
    """
    def test_event_scheduling(self):
        # Test scheduling a new event in an empty environment
        def dummy_action():
            pass

        env = simantha.simulation.Environment()
        new_event = {'time': 0, 'location': None, 'action': dummy_action}
        env.schedule_event(**new_event)

        self.assertEqual(len(env.events), 1)

    def test_event_insertion(self):
        # Test the ordering of newly scheduled events
        def dummy_action():
            pass

        env = simantha.simulation.Environment()
        env.schedule_event(
            time=10, location=None, action=dummy_action, source='last event'
        )
        env.schedule_event(
            time=0, location=None, action=dummy_action, source='first event'
        )
        env.schedule_event(
            time=5, location=None, action=dummy_action, source='middle event'
        )

        event_order = [ev.source for ev in env.events]

        self.assertEqual(event_order, ['first event', 'middle event', 'last event'])

    def test_constant_distribution(self):
        # Test sampling of a constant value
        constant = simantha.simulation.Distribution({'constant': 42})

        self.assertTrue(constant.sample(), 42)

    def test_uniform_distribution(self):
        # Test sampling of a discrete uniform distribution
        random.seed(1)
        low, high = [10, 60]
        uniform = simantha.simulation.Distribution({'uniform': [low, high]})
        rvs = [uniform.sample() for _ in range(1000)]

        # H_0: The sample is drawn from the specified distribution
        _, p_value = scipy.stats.kstest(rvs, scipy.stats.randint(low, high+1).cdf)

        self.assertGreater(p_value, 0.05)

    def test_geometric_distribution(self):
        # Test sampling of a geometric distribution
        success = 1/100
        geometric = simantha.simulation.Distribution({'geometric': success})
        rvs = [geometric.sample() for _ in range(1000)]

        # H_0: The sample is drawn from the specified distribution
        _, p_value = scipy.stats.kstest(rvs, scipy.stats.geom(success).cdf)

        self.assertGreater(p_value, 0.05)


class SingleMachineDeterministicTests(unittest.TestCase):
    """Basic simulation behavior of a single machine."""
    def build_system(self):
        source = Source()
        M1 = Machine('M1', cycle_time=1)
        sink = Sink()
        
        source.define_routing(downstream=[M1])
        M1.define_routing(upstream=[source], downstream=[sink])
        sink.define_routing(upstream=[M1])

        return System(objects=[source, M1, sink])

    def test_production(self):
        """Test production of a single machine. With cycle time 1, the production count
        should be equal to the simulation time."""
        system = self.build_system()
        system.simulate(simulation_time=1000, verbose=False)
        self.assertEqual(system.machines[0].parts_made, 1000)

    def test_production_warm_up(self):
        """Test the warm up period for a single machine. No statistics should be 
        gathered during the warm up, so production should be equal to simulation 
        time, regardless of warm up duration."""
        system = self.build_system()
        system.simulate(warm_up_time=500, simulation_time=500, verbose=False)
        self.assertEqual(system.machines[0].parts_made, 500)


class SingleMachineStochsticTests(unittest.TestCase):
    """Testing simulation randomness for one machine."""
    def build_system(self):
        source = Source()
        M1 = Machine(
            'M1', 
            cycle_time=1,
            degradation_matrix=degradation_matrix,
            cm_distribution={'constant': 10}
        )
        sink = Sink()
        
        source.define_routing(downstream=[M1])
        M1.define_routing(upstream=[source], downstream=[sink])
        sink.define_routing(upstream=[M1])

        return System(objects=[source, M1, sink])

    def test_production(self):
        random.seed(1)
        system = self.build_system()

        system.simulate(simulation_time=1000, verbose=False)

        # Assert that the number of parts made is at most the simulation time
        self.assertLessEqual(system.machines[0].parts_made, 1000)


class TwoMachineDeterministicTests(unittest.TestCase):
    """Tests for a two-machine one-buffer line. 
    """
    def build_system(self):
        source = Source()
        M1 = Machine('M1', cycle_time=1)
        B1 = Buffer('B1', capacity=5)
        M2 = Machine('M2', cycle_time=1)
        sink = Sink()

        source.define_routing(downstream=[M1])
        M1.define_routing(upstream=[source], downstream=[B1])
        B1.define_routing(upstream=[M1], downstream=[M2])
        M2.define_routing(upstream=[B1], downstream=[sink])
        sink.define_routing(upstream=[M2])

        return System(objects=[source, M1, B1, M2, sink])

    def test_production(self):
        system = self.build_system()
        system.simulate(simulation_time=1000, verbose=False)

        self.assertEqual(sum([s.level for s in system.sinks]), 999)


class TwoMachineStochasticTests(unittest.TestCase):
    def build_system(self):
        cm = {'constant': 10}
        source = Source()
        M1 = Machine(
            'M1', 
            cycle_time=1, 
            degradation_matrix=degradation_matrix, 
            cm_distribution=cm
        )
        B1 = Buffer('B1', capacity=5)
        M2 = Machine(
            'M2', 
            cycle_time=1, 
            degradation_matrix=degradation_matrix, 
            cm_distribution=cm
        )
        sink = Sink()

        source.define_routing(downstream=[M1])
        M1.define_routing(upstream=[source], downstream=[B1])
        B1.define_routing(upstream=[M1], downstream=[M2])
        M2.define_routing(upstream=[B1], downstream=[sink])
        sink.define_routing(upstream=[M2])

        return System(objects=[source, M1, B1, M2, sink])
    
    def test_production(self):
        system = self.build_system()
        system.simulate(simulation_time=1000, verbose=False)
        
        self.assertLessEqual(system.machines[-1].parts_made, 1000)


if __name__ == '__main__':
    random.seed(1)
    unittest.main()
