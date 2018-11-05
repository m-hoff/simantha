import simpy

import Machine
# import Buffer
# import Source
# import Sink

class System:
    '''
    Manufacturing system
    '''
    def __init__(self,
                 process_times,
                 interarrival_time=1, # int
                 buffer_sizes=1, # list or int

                 failures={'degradation':None, # list 
                           'reliability':None}, # scipy distribution
                 maintenance_policy=None, # CM/PM/CBM, str
				 maintenance_capacity=1,
                 maintenance_params=None, # define policy
                 maintenance_costs=None
                 )

		# specified system characteristics
        self.process_times = process_times
        self.interarrival_time = interarrival_time
        self.buffer_sizes = buffer_sizes

		self.failures = failures		
        self.maintenance_policy = maintenance_policy
		self.maintenance_capacity = maintenance_capacity
        self.maintenance_params = maintenance_params
        self.maintenance_costs = maintenance_costs

		# inferred system characteristics
		self.M = len(process_times) # number of machines
		self.bottleneck_rate = max(self.process_times)
		self.bottleneck = self.process_times.index(bottleneck_rate)
		
        self.initialize() # initialize system objects
		
	def initialize():
		# create simpy environment
		self.env = simpy.Environment()
	
		# create repairman object
		self.repairman = simpy.PriorityResource(self.env, capacity=self.maintenance_capacity)
	
		# create buffer objects
		#TODO
		self.buffers = [simpy.Container(self.env, capacity=]
	
		# create source object
	
		# create objects for each machine
		self.buffers = []
		self.machines = []
		
		index = 0
		for m in range(self.M):
			# buffer objects
			self.buffers += [simpy.Container(self.env, capacity=]
		
			# machine objects
			process_time = self.process_times[m]
			self.machines += [Machine(m, process_time, self.failures,
									  self.repairman)]

									  
									  
									  
									  
									  