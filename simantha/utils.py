import numpy as np

def generate_degradation_matrix(q, dim=10):
    degradation_matrix = np.eye(dim)
    for i in range(len(degradation_matrix - 1)):
        degradation_matrix[i, i] = 1 - q
        degradation_matrix[i, i+1] = q

    return degradation_matrix