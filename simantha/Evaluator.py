import time

from joblib import Parallel, delayed
import numpy as np
from pathos.multiprocessing import ProcessingPool as Pool

#from .System import *

class Evaluator:
    def __init__(self, system, warm_up_time, simulation_time):
        self.system = system
        self.warm_up_time = warm_up_time
        self.simulation_time = simulation_time

    def evaluate_policy(self, policy, replications ,objective='production', 
                        parallelize=True, verbose=True):
        # evalaute system under a given policy
        start_time = time.time()

        self.system.maintenance_policy = policy

        if parallelize:
            def simulate_in_parallel(seed):
                np.random.seed(seed)
                #return np.random.randint(min(seed,10),20)
                result = self.system.iterate_simulation(1, self.warm_up_time, 
                                        self.simulation_time, verbose=False)

                return result[0]  

            with Pool(min(24, replications)) as p:
                result = p.map(self.simulate_in_parallel, list(range(replications)))
            #result = Parallel(n_jobs=20)(delayed(self.simulate_in_parallel)(seed) 
            #                             for seed in range(replications))

        else:
            result = self.system.iterate_simulation(replications, self.warm_up_time,
                                                    self.simulation_time, verbose=False)

        stop_time = time.time()
        if verbose:
            print(f'Finished in {stop_time-start_time:.4f}s,',
                  f'{(stop_time-start_time)/replications:.4f}s/replication')                                                    

        return result

    def parallel_simulation_proxy(self, seed):
        np.random.seed(seed)

        result = self.system.iterate_simulation(1, self.warm_up_time,
                                         self.simulation_time, verbose=False)

        return result

    def simulate_in_parallel(self, seed):
        #result = self.system.iterate_simulation(1, self.warm_up_time, 
        #                                        self.simulation_time, verbose=False)

        result = list(self.parallel_simulation_proxy(seed))

        return result

        

def firstn(n):
    k = 0
    while k < n:
        yield k
        k += 1

def wrapped(n):
    return list(firstn(n))

def parallel_test():
    with Pool(10) as p:
        result = p.map(wrapped, list(range(10)))
    
    return result