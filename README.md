# maintsim

`maintsim` can be used to model a discrete manufacturing system where components degrade over time and recieve maintenance. Users can define the configuration and parameters of the system, as well as the maintenance policy to be carried out. It is built on the `SimPy` discrete-event simulation package.

## Installing maintsim

Currently, the easiest way to install maintsim is to clone the repository using `git clone https://github.com/m-hoff/maintsim.git`. 

## Using this package

### Requirements

maintsim relies on the following packages in addition to Python 3.7:

- [SimPy](https://simpy.readthedocs.io/en/latest/) version 3.0.11
- [pandas](https://pandas.pydata.org/) version >= 0.23.4
- [SciPy](https://www.scipy.org) version >= 1.1.0 (if specifying random repair times)
- [Graphviz](https://graphviz.readthedocs.io/en/stable/) version 0.10.1 (untested)

### Setting up a manufacturing system

The workflow begins by creating a `System` object that is defined by the following parameters:

#### Configuration parameters
- `process_times` - a list of process times for each machine in a serial line.
- `interarrival_time` - the time between part arrivals to the first machine in the system. The default is 1, which ensures the first machine is never starved.
- `buffer_sizes` - a list of buffer sizes for each machine, or an integer value for the buffer size of all machines. Default is 1. For n machines there are n-1 buffers.
- `initial_buffer` - a list of initial buffer levels for each buffer. By default buffers will begin empty.

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
  - Currently each machine has 11 health states, with 0 being perfect health and 10 being the failed state. The maintenance threshold should be in this range.
- `repair_params` - a dictionary of `scipy.stats` frozen discrete distributions of time to repair based on repair type.
  - For example, `repair_params = {'CM': stats.randint(10, 20), 'CBM': stats.randint(20, 40)}`.
- `maintenance_capacity` - the maximum number of maintenance jobs that can be executed simultaneously. Currently if the number of simultaneously scheduled maintenance jobs exceeds the capacity they will be handled in a first in, first out (FIFO) manner.
- `maintenance_costs` - a dictionary of the cost of each type of maintenance job by type.


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


### Other features

- The method `System.draw()` will display the system layout (only tested in jupyter notebooks).

## A simple example

Here is a minimum example for implmenting a CBM policy:

```python
>>> import maintsim
>>> from scipy import stats
>>> 
>>> system = maintsim.System(process_times=[3, 5, 4],
...                          buffer_sizes=5,
...                          failure_mode='degradation',
...                          failure_params=[0.25, 0.1, 0.2],
...                          maintenance_policy='CBM',
...                          maintenance_params={'CBM threshold': [8, 6, 7]},
...                          repair_params={'CM': stats.randint(20,30),
...                                         'CBM': stats.randint(10,20)},
...                          maintenance_capacity=1)
>>> system.simulate(warmup_time=100, sim_time=500)
Simulation complete in 0.89 s
 
  Units produced:      31
  System availability: 68.93%
```

## Planned features

Key planned features include

- Replication of the simulation to sample objective function values
- Support of a preventive maintenance policy, in which machines are repaired at regular intervals
- Non-homogeneous degradation modes and the ability to specify a complete degradation transition matrix
- Exporting system model for reuse
- Customizable `Scheduler` class for scenarios the number of machines due for maitnenance exceeds the maintenance capacity