import argparse
import unittest

import numpy as np
from scipy import stats

import maintsim

class ProductionTest(unittest.TestCase):
    '''
    Test expected production volume according to Little's Law.
    '''
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

    def test_production4(self):
        '''
        Test average throughput with degradation.
        '''
        repair_lower = 5
        repair_upper = 15
        system = maintsim.System(process_times=[5],
                                 failure_mode='degradation',
                                 failure_params={'failed state': 10,
                                                 'degradation rate': 0.2},
                                 repair_params={'CM': stats.randint(repair_lower,repair_upper+1)})

        time_horizon = 500

        # calculate true expected ttf (expected time to absorption)
        def expected_ttf(Q):
            M = Q[:-1, :-1]
            I = np.identity(len(M))
            N = np.linalg.inv(I - M)
            ones = np.ones(shape=(len(M), 1))
            t = np.matmul(N, ones)
            return t

        E_ttf = expected_ttf(system.machines[0].degradation)[0][0]

        # expected ttr
        E_ttr = (repair_lower + repair_upper) / 2

        A = E_ttf / (E_ttf + E_ttr)

        E_production = A * (time_horizon / system.machines[0].process_time)

        reps = 30
        production_samples = []
        for _ in range(reps):
            system.simulate(sim_time=time_horizon, verbose=False)
            production_samples.append(system.machines[0].parts_made)

        # conduct one sample t-test
        # H_0: average production sample = expected production
        # H_1: average production sample != expected production
        _, p_value = stats.ttest_1samp(production_samples, E_production)

        message = (f'Mean production is {np.mean(production_samples)}' + 
                   f' from {len(production_samples)} samples.' +
                   f' Expected mean: {E_production}') 
        self.assertGreaterEqual(p_value, 0.10, msg=message)            

    def test_degradation1(self):
        '''
        Test average time to failure of a single machine.
        '''
        system = maintsim.System(process_times=[5], 
                                 failure_mode='degradation',
                                 failure_params={'failed state': 10,
                                                 'degradation rate': 0.2},
                                 repair_params={'CM': stats.randint(2,3)})

        reps = 1
        warmup_time = 100
        time_horizon = 5000

        ttf_samples = np.array([])
        for _ in range(reps):
            system.simulate(warmup_time=warmup_time, sim_time=time_horizon, verbose=False)

            # gather ttf samples from simulation
            ttfs = system.maintenance_data[system.maintenance_data['activity'] == 'failure']['duration'].values
            ttfs = ttfs[ttfs != 'NA']
            np.append(ttf_samples, ttfs) 

        # calculate true expected ttf (expected time to absorption)
        def expected_ttf(Q):
            M = Q[:-1, :-1]
            I = np.identity(len(M))
            N = np.linalg.inv(I - M)
            ones = np.ones(shape=(len(M), 1))
            t = np.matmul(N, ones)
            return t

        E_ttf = expected_ttf(system.machines[0].degradation)[0][0]

        # conduct one sample t-test
        # H_0: average ttf sample = expected ttf
        # H_1: average ttf sample != expected ttf
        _, p_value = stats.ttest_1samp(ttf_samples, E_ttf)

        message = f'Mean TTF is {np.mean(ttf_samples)} from {len(ttf_samples)} samples'
        self.assertGreaterEqual(p_value, 0.10, msg=message)


if __name__ == '__main__':
    unittest.main()
