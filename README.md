# maintsim

`maintsim` can be used to model a discrete manufacturing system where components degrade over time and recieve maintenance. Users can define the configuration and parameters of the system, as well as the maintenance policy to be carried out. It is built on the `SimPy` discrete-event simulation package.

## Using this package

### Setting up a manufacturing system

The workflow begins by creating a `System` object that is defined by the following parameters:

#### Configuration parameters
- `process_times` - a list of process times for each machine in a serial line.
- `interarrival_time` - the time between part arrivals to the first machine in the system. The default is 1, which ensures the first machine is never starved.
- `buffer_sizes` - a list of buffer sizes for each machine, or an integer value for the buffer size of all machines. Default is 1. For n machines there are n-1 buffers.

#### Failure parameters
- `failure_mode` - currently either `'degradation'` or `None`. Each machine is subject to the same mode of degradation. By default machines do not degrade.
  - `'degradation'` - machine degradation occurs according to a discrete-state Markovian process.
- `failure_params` - for `'degradation'`, a list of transition probabilities between degradation states.
- `planned_failures` - a list of planned failures to occur during the simulation time. Each of the form `(location, time, duration)`. Planned failures do not adhere to maintenance capacity constraints and have not been thoroughly tested in tandom with random failures.

#### Maintenance parameters
- `maintenance_policy` - currently either `'CM'` or `'CBM'`.
  - `'CM'` - "corrective maintenance", the default policy, machines will only be repaired upon complete failure, as determined by the mode of degradation.
  - `'CBM'` - "condition-based maintenance", preventive maintenance is performed once a machine's condition reached a prescribed threshold.
- `maintenance_params` - the parameters that define the specified maintenance policy. For `CBM`, a list of thresholds at which to schedule maintenance.
- `repair_params` - a dictionary of `scipy.stats` frozen discrete distributions of time to repair based on repair type.
  - For example, `repair_params = {'CM': stats.randint(10, 20), 'CBM': stats.randint(20, 40)}`.
- `maintenance_capacity` - the maximum number of maintenance jobs that can be executed simultaneously. Currently if the number of simultaneously scheduled maintenance jobs exceeds the capacity they will be handled in a first in, first out (FIFO) manner.
- `maintenance_costs` - a dictionary of the cost of each type of maintenance job by type.

#### System state parameters

These parameters can be set to initialize the system state before simulation. By default the system begins with empty buffers and machines in perfect health. 
- `initial_remaining_process` - a list of remaining processing times for each machine. By default this is equal to the machine's total processing time when it does not have a part. 
- `initial_buffer` - a list of initial levels for each buffer. 
- `initial_health` - a list of initial health states for each machine.


### Creating a custom maintenance scheduler

The `System` object can take an additional `scheduler` object that will determine how maintenance jobs are scheduled when the number of machines due for maintenance exceeds the maintenance capacity. By default a system will use a FIFO scheduler as defined by the `Scheduler` class. A custom scheduler can also be created that inherits from the `maintsim.Scheduler` class. This new class should include a `choose_next` method that accepts the current maintenance queue as an argument. This method should then return a list of machine objects that are to be assigned maintenance. The `choose_next` method is executed each time a maintenance resource is release from a job.

An example of a custom scheduler that uses Monte Carlo tree search (as implemented by the [MCTS](https://github.com/pbsinclair42/MCTS) package) is shown below:

```python
import maintsim
import mcts

class MCTSScheduler(maintsim.Scheduler):
    '''
    Resolves maintenance scheduling conflicts using Monte Carlo tree search.
    '''
    def __init__(self, time_limit=None, iteration_limit=None, **kwds):
        '''
        Must specify either a time limit (in seconds) or iteration limit for the
        MCTS.
        '''
        super().__init__(**kwds)
        self.limit = {}
        if time_limit and iteration_limit:
            print('Error: cannot specify time and iteration limit.')
        elif time_limit:
            self.limit['timeLimit'] = time_limit * 1000
        else:
            self.limit['iterationLimit'] = iteration_limit

    def choose_next(self, queue):
        # formulate and solve MCTS
        mcts_schedule = mcts.mcts(**self.limit)
        best_action = mcts_schedule.search(initialState=MaintenanceState(self.system))
        next_machine = [self.system.machines[best_action-1]]

        return next_machine
```

### Simulating the system

When the system is instantiated, it will initialize by creating the necessary objects including the SimPy `Environment`, the maintenance resource, machines, and buffers. The simulation can be run by calling the `simulate` method of the `System` object with the following parameters:

- `title` - the tile of the simulation, used for naming any files that are saved.
- `warmup_time` - the time that the simulation will run before collecting data. Useful for ensuring the system is in steady state before observation.
- `sim_time` - the duration of time that simulation will run once the warmup is completed. Metrics will be determined based on the system performance during this time.
- `seed` - random seed for the simulation. A given seed should always produce the same results.
- `verbose` - boolean. `True` will print out a summary of the simulation run. `False` will suppress all printed output, which may be preferred if many replications are being run.


#### Simulation data

Several data frames are created to record data of a simulation run and stored as attributes of the `System` object.

- `state_data` - remaining processing time of each machine and buffer levels at each time step.
- `production_data` - production volume (in units) and throughput (in units/time) of each machine at every time step.
- `machine_data` - status of each machine at every time step, including if machines are function and blocked or starved.
- `queue_data` - the number of machines waiting for maintenance at each time step.
- `maintenance_data` - the log of maintenance activities including the time at which the activity occurred, the type of activity (corrective, preventive, etc.), what the activity was (failure or repair), and the duration or time to failure.

#### Iterating the simulation

A system can be simulated several times using the `System.iterate_simulation` method. The arguments for this method are:

- `replications` - number of times to run the simulation.
- `warmup_time` - the time that the simulation will run before collecting data. Performance statistics are only collected after this time has elapsed.
- `sim_time` - the duration of time each replication will be simulated.
- `objective` - the objective values that will be returned once all replications are complete. Options include:
  - `production` - the production volume in units of the system.
  - `ppl` - the permanent production loss of the system over the specified simulation time. 
  - `availability` - the overall availability of machines in the system as a percentage.
- `verbose` - `True` or `False`, determines whether or not summary statistics will be displayed once all replications are completed. 

### Other features

- The method `System.draw()` will display the system layout using the graphviz pacakge (only tested in jupyter notebooks).

---

### Planned features

Key planned features include

- Support of a preventive maintenance policy, in which machines are repaired at regular intervals
- Non-homogeneous degradation modes
- Exporting system model for reuse
