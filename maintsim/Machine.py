import simpy

class Machine:
    def __init__(self, 
				 env, 
				 m, 
				 process_time, 
				 degradation, 
				 planned_failures,
				 system, 
				 repairman):
				 
		self.env = env
		self.m = m
		self.process_time = process_time
		self.degradation = degradation
		self.planned_failures = planned_failures
		self.system = system
		self.repairman = repairman
		
		# determine maintenance policy for machine
		self.maintenance_policy = self.system.maintenance_policy
		maintenance_parameters = self.system.maintenance_parameters
		if self.maintenance_policy == 'PM':
			self.PM_interval = maintenance_parameters['PM interval'][self.m]
			self.PM_duration = maintenance_parameters['PM duration'][self.m]
		elif self.maintenance_policy == 'CBM':
			self.CBM_threshold = maintenance_parameters['CBM threshold'][self.m]
		
		# assign input buffer
		if self.m > 0:
			self.in_buff = self.system.buffers[self.m-1]
			
		# assign output buffer
		if (self.m < self.system.M-1):
			self.out_buff = self.system.buffers[m]
		
		# set initial machine state
		# maintenance state
		self.health = 0
		self.awaiting_maintenance = False
		self.failed = False
		self.repair_type = None
		# production state
		self.has_part = False
		self.parts_made = 0