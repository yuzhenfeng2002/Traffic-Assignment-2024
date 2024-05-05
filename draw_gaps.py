import numpy as np
import matplotlib.pyplot as plt

def moving_average(interval, windowsize):
    window = np.ones(int(windowsize)) / float(windowsize)
    re = np.convolve(np.log10(interval), window, 'same')
    return np.power(10, re)

CFW = np.loadtxt("./iteration_gaps/SiouxFalls_CFW_gaps.csv")
FW = np.loadtxt("./iteration_gaps/SiouxFalls_FW_gaps.csv")
MSA = np.loadtxt("./iteration_gaps/SiouxFalls_MSA_gaps.csv")
NT = np.loadtxt("./iteration_gaps/SiouxFalls_NT_gaps.csv")

windowsize = 20
CFW = moving_average(CFW, windowsize)[:-windowsize]
FW = moving_average(FW, windowsize)[:-windowsize]
MSA = moving_average(MSA, windowsize)[:-windowsize]
NT = moving_average(NT, windowsize)[:-windowsize]

fig, ax = plt.subplots()
ax.plot(FW, label="FW")
ax.plot(MSA, label="MSA")
ax.plot(CFW, label="CFW")
ax.plot(NT, label="NT")
ax.legend()
ax.set_yscale("log")
plt.show()