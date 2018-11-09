import simpy
from random import random

from Globals import G

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
		self.health = 0 # starts in perfect health
		self.awaiting_maintenance = False
		self.failed = False
		self.repair_type = None
		# production state
		self.has_part = False
		self.parts_made = 0
		
	def working(self, repairman):
		'''
		Main production function. Machine will produce parts
		until interrupted by failure. 
		'''
		prev_part = 0
		while True:
			try:
				idle_start = idle_stop = 0
				
				# get part from input buffer
				if self.m > 0: 
					idle_start = self.env.now - G.warmup_time
					yield self.in_buff.get(1)
					idle_stop = self.env.now - G.warmup_time
					self.has_part = True
					self.remaining_process_time = self.process_time
					
				# check if machine was starved
				if idle_stop - idle_start > 0:
					# TODO: record idle time
					pass
					
				# process part
				for t in range(self.process_time):
					# TODO: record processing
					yield self.env.timeout(1)
					self.remaining_process_time -= 1
					
				# put finished part in output buffer
				idle_start = idle_stop = 0
				if self.m < self.system.M-1:
					idle_start = self.env.now - G.warmup_time
					yield self.out_buff.put(1)
					idle_stop = self.env.now - G.warmup_time
					self.has_part = False
					
				# check if machine was blocked
				if idle_stop - idle_start > 0:
					# TODO: record idle time
					pass
					
				if self.env.now > G.warmup_time:
					self.parts_made += 1
					# TODO: record parts made
					prev_part = self.env.now
			
			except simpy.Interrupt: 
				# processing interrupted due to failure
				self.broken = True
				self.has_part = False
				
				# TODO: fix this
				time_to_repair = 10
				
				with repairman.request(priority=1) as req:
					yield req
					yield self.env.timeout(time_to_repair)
					# TODO: record maintenance data
				
				self.health = 0
				self.broken = False
				
				# TODO: record more maintenance data
	
	def degrade(self):
		'''
		Discrete state degradation process. 
		'''
		while True:
			while random() > self.degradation:
				# do NOT degrade
				yield self.env.timeout(1)
				# TODO: check planned failures
			
			# degrade by one unit once loop breaks
			yield self.env.timeout(1)
			
			if self.health < 10:
				# machine is NOT failed
				self.health += 1
				
				if self.health == 10: # machine fails
					self.broken = True
					self.repair_type = 'CM'
					self.process.interrupt()
					
				elif (self.maintenance_policy == 'CBM') and (self.health == self.CBM_threshold):
					# TODO schedule preventive maintenance
					self.repair_type = 'CBM'
					# self.process.interrupt() (?)
					pass
					
			
			
		