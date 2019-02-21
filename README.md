## maintsim
### Simulation of the operation and maintenance of manufacturing systems

`maintsim` can be used to model a discrete manufacturing system where components degrade over time and recieve maintenance. Users can define the configuration and parameters of the system, as well as the maintenance policy to be carried out. It is built on the `SimPy` discrete-event simulation package. 

The workflow begins by creating a `System` object that is defined by the following parameters:

- `process_times` - a list of process times for each machine in a serial line
- `interarrival_time` - the time between part arrivals to the first machine in the system. The default is 1, which ensures the first machine is never starved.
- `buffer_sizes` - a list of buffer sizes for each machine, or an integer value for the buffer size of all machines. Default is 1. 
- `degradation` - a list of degradation rates for each machine (between 0 and 1), or a value to be used for all machines. Default is no degradation. 
- `planned_failures` - a list of planned failures to occur during the simulation time. Each of the form (location, time, duration).
- `maintenance_policy` - `'CM'` for corrective maintenance, `'PM'` for preventive maintenance, or `'CBM'` for condition-based maintenance. 
- `maintenance_params` - the parameters that define the specified maintenance policy. 
- `maintenance_capacity` - the maximum number of maintenance jobs that can be executed simultaneously. 
- `maintenance_costs` - the cost of each type of maintenance job.

When the system is instantiated, it will initialize by creating the necessary objects including the SimPy `Environment`, the maintenance resource, machines, and buffers. To simulate, call the `simulate` method of the system object, passing the following parameters:

- `title` - the tile of the simulation, used for naming any files that are saved. 
- `warmup_time` - the time that the simulation will run before collecting data.
- `sim_time` - the duration of time that simulation will run once the warmup is completed. 
- `seed` - random seed for the simulation. A given seed will always produce the same results.
- `verbose` - boolean. `True` will print out a summary of the simulation run. `False` will suppress all printed output, which may be preferred if many replications are being run. 

