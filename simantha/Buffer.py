class Buffer:
    def __init__(self, name='Buffer', capacity=float('inf'), initial_level=0):
        self.name = name
        self.capacity = capacity
        self.initial_level = initial_level
        self.level = initial_level

        self.env = None

        self.level_data = {'time': [0], 'level': [initial_level]}

        self.pending_requests = []

    def initialize(self):
        self.level = self.initial_level
        
        self.reserved_content = 0
        self.reserved_vacancy = 0

        if self.env.collect_data:
            self.level_data = {'time': [0], 'level': [self.initial_level]}

    def can_get_part(self):
        return self.level + self.reserved_vacancy < self.capacity

    def reserve_content(self, quantity=1):
        self.reserved_content += 1
        
    def get(self, quantity=1):
        if not self.is_empty():
            self.level -= quantity
            self.reserved_content -= quantity

            if self.env.collect_data:
                self.level_data['time'].append(self.env.now)
                self.level_data['level'].append(self.level)

        else:
            raise RuntimeError('Attempting to take more parts than available.')

    def reserve_vacancy(self, quantity=1):
        self.reserved_vacancy += 1
            
    def put(self, quantity=1):
        if not self.is_full():
            self.level += quantity
            self.reserved_vacancy -= 1

            if self.env.collect_data:
                self.level_data['time'].append(self.env.now)
                self.level_data['level'].append(self.level)

        else:
            raise RuntimeError('Attempting to put part in full buffer.')
    
    def is_empty(self):
        #return self.level - self.reserved_content == 0
        return self.level == 0
    
    def is_full(self):
        #return self.level + self.reserved_vacancy == self.capacity
        return self.level == self.capacity

    def can_give(self):
        return self.level - self.reserved_content > 0

    def can_receive(self):
        return self.level + self.reserved_vacancy < self.capacity

    # def get_available_space(self):
    #     return self.capacity - self.level
    
    # def get_available_parts(self):
    #     return self.level
    
    def define_routing(self, upstream=[], downstream=[]):
        self.upstream = upstream
        self.downstream = downstream

    def get_candidate_givers(self, only_free=False, blocked=False):
        if blocked:
            # get only candidate givers that can give a part
            return [obj for obj in self.get_candidate_givers() if obj.blocked]
        else:
            return [obj for obj in self.upstream if obj.can_give()]

    def get_candidate_receivers(self, only_free=False, starved=False):
        if starved:
            return [obj for obj in self.get_candidate_receivers() if obj.starved]
        else:
            # get only candidate receivers that can accept a part
            return [obj for obj in self.downstream if obj.can_receive()]
        