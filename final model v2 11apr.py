# -*- coding: utf-8 -*-
"""
Created on Mon Mar 28 13:37:55 2016

@author: Ovidiu & Maria

working model without time intervals
"""
import time
import csv
from itertools import tee, islice
from pulp import *
import pandas

# save starting time of program
start_time = time.clock()

# Create a list of all possible workstations (chute patterns)
def slices(iterable):
    wst = []
    for n in range(1,4):
        wst = wst + list(zip(*(islice(it, i, None) for i, it in enumerate(tee(iterable, n)))))
    return list(wst)

# Function to read from csv filename to dictionary dictname
def read_file(filename, dictname):
    with open(filename, 'r') as f:
        # Get the CSV reader and skip header
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
           #First column is the key, the rest is value
           dictname[row[0]] = row[1:]
           # Print result
           # print(row[0], ':', dictname[row[0]])

chute_groups = {}
read_file('chute_groups.csv', chute_groups)

# separate the chute groups dictionary into items, assign name and chutes to workstations
def separate_chutes(k, iterable, dictname):
    dictname[k, iterable[0],iterable[1]] = slices(iterable[2:])
    
separated_chutes = {}
for k, v in chute_groups.items():
    separate_chutes(k, v, separated_chutes)

i = 1
j = 1
workstations = {}
for k, v in separated_chutes.items():
    for item in v:
        if k[1] == 'FLX':
            workstations['wf'+str(i)] = (k[1], k[2], item)
            i += 1
        else:
            workstations['w'+str(j)] = (k[1], k[2], item)
            j += 1
                
# Read flight departures from csv file
flights = {}
read_file('100_busy.csv', flights)

# get a list of all flights       
departures = list(flights.keys())

# Generate C dictionary - penalty of assining flight f at time t to workstation w
c = {}
for f, ft in flights.items():
    for w, wchutes in workstations.items():
        c[ft[0], f, w] = 0
        step = int(ft[3]) - len(wchutes[2])
        if ft[1] == wchutes[0]:
            if ft[2] == 'BULK' and wchutes[1] == 'low' or ft[2] == 'ULD' and wchutes[1] == 'high':
                if step == 0:
                    c[ft[0], f, w] = 1
            elif ft[2] in ('BULK', 'ULD') and wchutes[1] == 'medium':
                if step == 0:
                    c[ft[0], f, w] = 2
        elif wchutes[0] == 'FLX':
            if ft[2] == 'BULK' and wchutes[1] == 'low' or ft[2] == 'ULD' and wchutes[1] == 'high':
                if step == 0:
                    c[ft[0], f, w] = 100
            elif ft[2] in ('BULK', 'ULD') and wchutes[1] == 'medium':
                if step == 0:
                    c[ft[0], f, w] = 200
                    
# Generate D dictionary to show which chutes are in which workstations
chutes = []
for w in workstations.values():
    chutes.append(w[2])
chutes = sorted(list(set(itertools.chain(*chutes))), key=int)

d = {}
for ch in chutes:
    for k, v in workstations.items():
        if ch in v[2]:
            d[k, ch] = 1
        else:
            d[k, ch] = 0

times = sorted(list(set(ft[0] for ft in flights.values())))

x = pulp.LpVariable.dicts('x', [(t, f, w) for t in times for f in flights.keys() \
    for w in workstations.keys()], 0, 1, LpBinary)

# Declare pulp model
chute_allocation = pulp.LpProblem('Chute Allocation', pulp.LpMinimize)

# Objective function
chute_allocation += lpSum(c[(ft[0], f, w)] * x[(ft[0], f, w)] \
    for f,ft in flights.items() for w in workstations.keys())

# Constraints
# all flights must be assigned to one workstation
for f, ft in flights.items():
    chute_allocation += lpSum(x[(ft[0], f, w)] for w in workstations.keys()) == 1

# a workstation can only be assigned once per each t
for w in workstations.keys():
    for t in times:
        chute_allocation += lpSum(x[(t, f, w)] for f, ft in flights.items() \
            if ft[0] == t) <= 1

# only assign a flight if it is allowed by C matrix
for f, ft in flights.items():
    for w in workstations.keys():
        chute_allocation += x[(ft[0], f, w)] <= c[(ft[0], f, w)]
        

# a chute cannot be in more than one workstation that is allocated at time t
for ch in chutes:
    for t in times:
        chute_allocation += lpSum(d[(w, ch)] * x[(t, f, w)] \
        for f, ft in flights.items() if t == ft[0] \
        for w, wchutes in workstations.items() if ch in wchutes[2]) <= 1

# solve the model and write to txt
chute_allocation.solve()
chute_allocation.writeLP("LPalloc.txt")



print("problem status " + str(chute_allocation.status))
print("total penalty ", value(chute_allocation.objective))

# transfer results from x lpvariable to dataframe
result = {}
for k, v in x.items():
    result[k] = value(v)
result = pandas.Series(result).unstack()

"""
# print unique chute constraint
for ch in chutes:
    for t in times:
        ch_sum = 0
        for f, ft in flights.items():
            for w, wchutes in workstations.items():
                print(d.get_value(ch, w[0]) * value(x[(t, f, wchutes)]))
                ch_sum += d.get_value(ch, w[0]) * value(x[(t, f, wchutes)])
        if ch_sum > 0:
            print(ch_sum, ch, t)
"""        

# write results to txt file
allocation_out = open('allocout.txt','w')
count = 0
flex_count = 0
for f, ft in flights.items():
    for w, wchutes in workstations.items():
        if value(x[(ft[0], f, w)]) == 1:
            if 'wf' in w:
                flex_count += 1
            allocation_out.write(f + str(ft) + " assigned to " + \
                str(w) + str(wchutes) + " with a penalty of " \
                + str(c[(ft[0], f, w)])+ '\n')
            count += 1
print("flights allocated ", count, " of which ", flex_count, " in flexible workstations")

allocation_out.write('-----------------------------------------------------\n')

workstation_count = {}
for w, wchutes in workstations.items():
    workstation_count[w] = 0
    for f, ft in flights.items():
        if value(x[(ft[0], f, w)]) == 1:
            workstation_count[w] += 1
    if workstation_count[w] > 0:
        allocation_out.write("workstation " + str(w) + " with " + str(wchutes) \
            + " assigned to " + str(workstation_count[w]) + ' flights\n')
print("most flights allocated to one workstation ", max(workstation_count.values()))

# a chute cannot be in more than one workstation that is allocated at time t
for t in times:
    assigned_chutes = []
    for f, ft in flights.items():
        if t == ft[0]:
            for w, wchutes in workstations.items():
                if value(x[(t, f, w)]) == 1:
                    assigned_chutes.append(wchutes[2])
    assigned_chutes = list(itertools.chain(*assigned_chutes))
    if len(assigned_chutes) != len(set(assigned_chutes)):
        allocation_out.write("duplicate chutes at " + str(t) + '_' + str(assigned_chutes) + '\n')

# close file after writing  
allocation_out.close()            

# print elapsed time
print("--- %s seconds ---" % round((time.clock() - start_time), 3))
