import random

class Asset:
    """
    Parent class for assets in the system. All objects should extend this class, and
    there should be no instances.
    """
    def __init__(self, name, selection_priority=1):
        self.name = name
        # assets with higher priority will be selected over those with lower priority
        # when competing for resources or space. 
        self.selection_priority = selection_priority

        self.upstream = []
        self.downstream = []

    def initialize(self):
        pass

    def get_candidate_givers(self, blocked=False):
        """
        Returns a list of assets that can give a part to this asset from among the
        upstream assets. 

        If 'blocked=True' then only return assets that are currently blocked. 
        """
        candidates = []
        for candidate in self.upstream:
            if blocked:
                if candidate.blocked:
                    candidates.append(candidate)
