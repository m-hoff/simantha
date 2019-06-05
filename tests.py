import argparse
import unittest

import maintsim

class ProductionTest(unittest.TestCase):
    '''
    Test expected production volume according to Little's Law.
    '''
    # def __init__(self):
    #     self.system = maintsim.System(process_times=[5])

    def test_production1(self):
        '''
        Production volume of one machine.
        '''
        time_horizon = 500
        cycle_time = 5
        expected_production = time_horizon / cycle_time

        system = maintsim.System(process_times=[cycle_time])
        system.simulate(sim_time=time_horizon, verbose=False)

        self.assertEqual(system.machines[-1].parts_made,
                         expected_production,
                         'Should be {}'.format(expected_production))

    def test_production2(self):
        '''
        Production volume of one machine.
        '''
        time_horizon = 500
        cycle_time = 10
        expected_production = time_horizon / cycle_time

        system = maintsim.System(process_times=[cycle_time])
        system.simulate(sim_time=time_horizon, verbose=False)

        self.assertEqual(system.machines[-1].parts_made,
                         expected_production,
                         'Should be {}'.format(expected_production))

    def test_production3(self):
        '''
        Production volume of a two-machine line.
        '''
        time_horizon = 500
        cycle_times = [5, 3]
        expected_production = time_horizon / max(cycle_times)

        system = maintsim.System(process_times=cycle_times)
        system.simulate(warmup_time=100, sim_time=time_horizon, verbose=False)

        self.assertAlmostEqual(system.machines[-1].parts_made,
                               expected_production,
                               msg=f'Should be {expected_production}+/-1',
                               delta=1)

if __name__ == '__main__':
    unittest.main()
