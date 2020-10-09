import unittest

from simantha import Source, Machine, Buffer, Sink, System, utils
import simantha.simulation

class SimulationTests(unittest.TestCase):
    """Tests for the underlying simulation engine. 
    """
    def test_event_scheduling(self):
        # Test scheduling a new event in an empty environment
        env = simantha.simulation.Environment()
        new_event = {'time': 0, 'location': None, 'action': None}
        env.schedule_event(**new_event)

        self.assertEqual(len(env.events), 1)

    

class SingleMachineTests(unittest.TestCase):
    """Basic simulation behavior of a single machine.
    """
    def build_system(self):
        source = Source()
        M1 = Machine('M1', cycle_time=1)
        sink = Sink()
        
        source.define_routing(downstream=[M1])
        M1.define_routing(upstream=[source], downstream=[sink])
        sink.define_routing(upstream=[M1])

        return System(objects=[source, M1, sink])

    def test_production(self):
        system = self.build_system()
        system.simulate(simulation_time=1000, verbose=False)
        self.assertEqual(system.machines[0].parts_made, 1000)

    def test_warm_up(self):
        system = self.build_system()
        system.simulate(warm_up_time=500, simulation_time=500, verbose=False)
        self.assertEqual(system.machines[0].parts_made, 500)

class TwoMachineOneBufferTests(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
