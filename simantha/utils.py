def generate_degradation_matrix(p, h_max):
    degradation_matrix = []
    for h in range(h_max):
        transitions = [0] * (h_max + 1)
        transitions[h] = 1 - p
        transitions[h+1] = p
        degradation_matrix.append(transitions)
    degradation_matrix.append([0]*h_max + [1])
    return degradation_matrix

# date constants (in minutes)
DAY = 24 * 60
WEEK = 7 * DAY
MONTH = 30 * DAY
YEAR = 365 * DAY
