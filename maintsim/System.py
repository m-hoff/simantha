import simpy

import Machine
# import Buffer
# import Source
# import Sink

class System:
    '''
    Manufacturing system class
    '''
    def __init__(self,
                 process_times,
                 interarrival_time=1, # int
                 buffer_sizes=1, # list or int

                 failures={'degradation':None, # list 
                           'reliability':None}, # scipy distributions
				 degradation=None, # list or int of degradation rate
				 planned_failures=None, # list of (loc, time, duration)
                 maintenance_policy=None, # CM/PM/CBM, str
                 maintenance_params=None, # define policy
				 maintenance_capacity=1,
                 maintenance_costs=None):

		# specified system characteristics
        self.process_times = process_times
        self.interarrival_time = interarrival_time
        if type(self.buffer_sizes) == int:
			self.buffer_sizes = [buffer_sizes]*(len(process_times)-1)
		else:
			self.buffer_sizes = buffer_sizes
		self.failures = failures	
		if type(self.degradation) == int:
			self.degradation = [degradation]*(len(process_times))
		else:
			self.degradation = degradation
		self.planned_failures = planned_failures
        self.maintenance_policy = maintenance_policy
		self.maintenance_params = maintenance_params
		self.maintenance_capacity = maintenance_capacity
        self.maintenance_costs = maintenance_costs

		# inferred system characteristics
		self.M = len(process_times) # number of machines
		self.bottleneck_rate = max(self.process_times)
		self.bottleneck = self.process_times.index(bottleneck_rate)
		
        self.initialize() # initialize system objects
		
		# simulation parameters
		self.warmup_time = 0
		
	def initialize():
		# create simpy environment
		self.env = simpy.Environment()
	
		# create repairman object
		self.repairman = simpy.PriorityResource(self.env, capacity=self.maintenance_capacity)
	
		# create source object
	
		# create objects for each machine
		self.buffers = []
		self.machines = []
		
		for m in range(self.M):
			# buffer objects
			if m < (self.M - 1):
				self.buffers += [simpy.Container(self.env, capacity=self.buffer_sizes[m])]
			
			# planned failures for m
			planned_falures_m = [DT for DT in self.planned_failures if DT[0] == m]
			
			# machine objects
			process_time = self.process_times[m]
			self.machines += [Machine(self.env, m, process_time, degradation[m],
									  planned_failures_m, self, self.repairman)]

									  
		# initialize system data collection							  
									  
									  
									  
									  
									  
									  
									  
									  
									  
									  