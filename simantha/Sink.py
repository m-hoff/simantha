class Sink:
    def __init__(self, name='Sink', initial_level=0):
        self.name = name
        self.capacity = float('inf')
        self.initial_level = initial_level
        self.level = initial_level

        self.selection_priority = 1 

        self.env = None

        # self.level_data = {'time': [0], 'level': [initial_level]}

    def initialize(self):
        self.level = self.initial_level

    def reserve_vacancy(self, quantity=1):
        return

    def put(self, quantity=1):
        if self.env.now > self.env.warm_up_time:
            self.level += quantity

        # self.level_data['time'].append(self.env.now)
        # self.level_data['level'].append(self.level)

    def define_routing(self, upstream=[], downstream=[]):
        self.upstream = upstream
        self.downstream = downstream

    def can_give(self):
        return False

    def can_receive(self):
        return True
