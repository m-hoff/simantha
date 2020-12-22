<<<<<<< HEAD
import numpy as np

def generate_degradation_matrix(q, dim=10):
    degradation_matrix = np.eye(dim)
    for i in range(len(degradation_matrix - 1)):
        degradation_matrix[i, i] = 1 - q
        degradation_matrix[i, i+1] = q

    return degradation_matrix
=======
def generate_degradation_matrix(p, h_max):
    # Returns an upper bidiagonal degradation matrix with probability p of degrading at
    # each time step.
    degradation_matrix = []
    for h in range(h_max):
        transitions = [0] * (h_max + 1)
        transitions[h] = 1 - p
        transitions[h+1] = p
        degradation_matrix.append(transitions)
    degradation_matrix.append([0]*h_max + [1])
    return degradation_matrix

# Time constants (in minutes)
DAY = 24 * 60
WEEK = 7 * DAY
MONTH = 30 * DAY
YEAR = 365 * DAY
>>>>>>> dev
