import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Times New Roman'

def moving_average(interval, windowsize):
    window = np.ones(int(windowsize)) / float(windowsize)
    re = np.convolve(np.log10(interval), window, 'same')
    return np.power(10, re)

CFW = np.loadtxt("./iteration_gaps/SiouxFalls_CFW_gaps.csv")
FW = np.loadtxt("./iteration_gaps/SiouxFalls_FW_gaps.csv")
MSA = np.loadtxt("./iteration_gaps/SiouxFalls_MSA_gaps.csv")
GP = np.loadtxt("./iteration_gaps/SiouxFalls_GP_gaps.csv")
GP_E = np.loadtxt("./iteration_gaps/SiouxFalls_GP-E_gaps.csv")

windowsize = 50
CFW_i = moving_average(CFW[:, 1], windowsize)[:-windowsize]
FW_i = moving_average(FW[:, 1], windowsize)[:-windowsize]
MSA_i = moving_average(MSA[:, 1], windowsize)[:-windowsize]
GP_i = moving_average(GP[:, 1], windowsize)[:-windowsize]
GP_E_i = moving_average(GP_E[:, 1], windowsize)[:-windowsize]

_, ax = plt.subplots(dpi=600)
ax.plot(FW_i, label="FW (ELS)", linestyle='-')
ax.plot(MSA_i, label="FW ($\\alpha=\\frac{2}{k+2}$)", linestyle='-')
ax.plot(CFW_i, label="CFW", linestyle='-')
ax.plot(GP_E_i, label="GP (ELS)", linestyle='-')
ax.plot(GP_i, label="GP ($\\alpha=0.05$)", linestyle='-')
ax.legend()
ax.set_yscale("log")
ax.set_xlabel('Iteration')
ax.set_ylabel('Gap')
ax.set_ylim(1e-6, 1e-2)
ax.set_xlim(0, 5000)
plt.show()

def moving_average_normal(interval, windowsize):
    window = np.ones(int(windowsize)) / float(windowsize)
    re = np.convolve(interval, window, 'same')
    return re

windowsize = 50
CFW_t = moving_average_normal(CFW[:, 0], windowsize)[:-windowsize]
FW_t = moving_average_normal(FW[:, 0], windowsize)[:-windowsize]
MSA_t = moving_average_normal(MSA[:, 0], windowsize)[:-windowsize]
GP_t = moving_average_normal(GP[:, 0], windowsize)[:-windowsize]
GP_E_t = moving_average_normal(GP_E[:, 0], windowsize)[:-windowsize]
CFW_j = moving_average(CFW[:, 1], windowsize)[:-windowsize]
FW_j = moving_average(FW[:, 1], windowsize)[:-windowsize]
MSA_j = moving_average(MSA[:, 1], windowsize)[:-windowsize]
GP_j = moving_average(GP[:, 1], windowsize)[:-windowsize]
GP_E_j = moving_average(GP_E[:, 1], windowsize)[:-windowsize]

_, ax = plt.subplots(dpi=600)
ax.plot(FW_t, FW_j, label="FW (ELS)", linestyle='-')
ax.plot(MSA_t, MSA_j, label="FW ($\\alpha=\\frac{2}{k+2}$)", linestyle='-')
ax.plot(CFW_t, CFW_j, label="CFW", linestyle='-')
ax.plot(GP_E_t, GP_E_j, label="GP (ELS)", linestyle='-')
ax.plot(GP_t, GP_j, label="GP ($\\alpha=0.05$)", linestyle='-')
ax.legend()
ax.set_yscale("log")
ax.set_xlabel('Time (s)')
ax.set_ylabel('Gap')
ax.set_ylim(1e-6, 1e-2)
ax.set_xlim(0, 100)
plt.show()