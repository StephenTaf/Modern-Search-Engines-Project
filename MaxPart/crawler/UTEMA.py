import time
import matplotlib.pyplot as plt
import numpy as np
import math


##################################
# The UNBIASED TIME- EXPONENTIAL MOVING AVERAGE 
################################ 
# The functions in this file all have to do with the calculating of the UTEMA a weighted
# average that is described in detail in this Paper from Menth and Hauser: On Moving Averages, Histograms and Time- Dependent
# Rates for Online Measurement, IPCE'17, 2017 ((https://atlas.cs.uni-tuebingen.de/~menth/papers/Menth17c.pdf) 
#----------------------------

#======================================================================
#testing done?: Yes, everything works as expected!
#======================================================================


# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage is finished and there probably won't be any additions in the future
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


#............................
# helpers specifically for this task
#............................


# this function here is just for plotting response- data, given a domain-name with a list of pairs (responseTime, delay-time)
def plotResponses(responseTimeData,style):
    time = 0
    y = [item[1] for item in responseTimeData]
    x = [item[0] for item in responseTimeData]

    for item in x:
        time = time + item
        item = time
        
    plt.plot(x, y, style)
    plt.xlabel('timeline of data points')
    plt.ylabel('response Time')




# given a series utilises UTEMA (Unbiased  Exponential Moving Average, from Menth et al.: "On moving Averages, Histograms and Time- Dependent
# Rates for Online Measurement (https://atlas.cs.uni-tuebingen.de/~menth/papers/Menth17c.pdf))
# Note that cases t<t_0 and t <t_i < t_{i+1} are ignored for the calculation of S and N, since we only measure  (approximately) as
# soon as we have a new data point
def UTEMA(nameOfField,value, dict):
    t = time.time()
    beta = 1/5
    if nameOfField not in dict:
        dict[nameOfField] = None
    if "S_last" not in dict[nameOfField] :
        # this will be the final weighted the average A after inclusion of the current data point
        A = 0
        # these are the Values for S and N in case t = t_0
        S = value
        N = 1 
        # --- measures time since a certain arbitrary point,at some moment somewhen before the start of the program
        # --- time is measured in seconds
        dict[nameOfField]["S_last"] = S
        dict[nameOfField]["N_last"] = N
        dict[nameOfField]["t_last"] = t
   
    if dict[nameOfField] != None:
    # these are the cases t= t_i 
        S = dict[nameOfField]["S_last"]
        N = dict[nameOfField]["N_last"]
        t_last = dict[nameOfField]["t_last"]
        expWeight = math.exp(- beta *(t - t_last))

        S = expWeight * S + value
        N = expWeight * N + 1

    # updating the values in responseTime
    dict[nameOfField]["S_last"] = S
    dict[nameOfField]["t_last"] = t
    dict[nameOfField]["N_last"] = N

    # calculation of A 
    A = S / N

    return A








#............................
# tests
#............................


# this function is just for generating random Data in order to testplotResponses and plot the data as well
def testData(a):
    # just part of the test if UTEMA works correctly
    # global randomDelays
    delayList = np.random.uniform(10**(-6),2* 10**(-6),10**6)
    valueList = np.random.exponential(a, 10**6)
    dataPointsx = []
    dataPointsy = []



    
    responses = []
    
    responseTimes = {"test":{}}

    for index in range(len(delayList)):
        responses.append([0,UTEMA("test", valueList[index], responseTimes)])
        time.sleep(delayList[index])
        responses[index] [0] = responseTimes["test"]["t_last"] 
        dataPointsx.append(responseTimes["test"]["t_last"])
        dataPointsy.append(valueList[index])




    plt.figure()
    plotResponses(responses, '--r')
    plt.figure()
    plt.plot(dataPointsx, dataPointsy)
    plt.xlabel('timeline of data points')
    plt.ylabel('response Time')
    
        

# this is just to test if UTEMA works correctly:
# testData(4)
# plt.show()
#print(responseTimes["test"]["S_last"] / responseTimes["test"]["N_last"])
#randomDelays = np.array(randomDelays)
# print(np.mean(randomDelays))