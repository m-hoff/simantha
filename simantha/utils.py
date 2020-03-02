import numpy as np

def create_degradation_matrix(failed_state, degradation_rate=0):
    degradation_matrix = np.eye(failed_state+1)
    for i in range(failed_state):
        degradation_matrix[i, i] = 1 - degradation_rate
        degradation_matrix[i, i+1] =  degradation_rate
    return degradation_matrix
    