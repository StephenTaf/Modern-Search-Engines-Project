import requests
import bisect #module for binary search
import time
import matplotlib.pyplot as plt
import numpy as np
import math

###############################################
# only for testing
headers = {
    "User-Agent": "DSEUniProjectCrawler/1.0 (contact: poncho.prime-3y@icloud.com)", 
    #We don't have a webpage for our crawler
    "From": "poncho.prime-3y@icloud.com",
    # the different formats our crawler accepts and the preferences
    "Accept": "text/html,application/xhtml+xml q= 0.9,application/xml;q=0.8,*/*;q=0.7",
    # the languages our crawler accepts
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    #keeping the connection alive, so we do not need a new TCP handshake for each request
    "Connection": "keep-alive"
}

url = "https://www.yale.edu/robots.txt"

response = requests.get(url, headers=headers)


# returns a dictionary of form {delay: <delay value>,explicitely allowed pages: <DictionaryOfPages> forbidden pages: <DictionaryOfPages>}}





#counts the number of lines starting with Disallow (as it happens, the yale website only has one agent specified,
# namely the general one):
allowdCount = response.text.count("Disallow:")
#print(f"So many 'Allow''s are in the text {allowdCount}")

###############################################

###### some global variables ########
# for the meaning of weighted Sample Sum, weighted Sample Number, Last time-point (t_{i-1}) see the paper in the commentary of UTEMA
''' data structure used by UTEMA '''
# <domain> :{"S_last": <=weightedSampleSum>,"N_last": <weightedSampleNumber> "t_last":<lastTimePoint>, ""}
responseTimes = {}

####### just for testing of UTEMA:
randomDelays = []



# adds a new item to an already lexicographically ordered list
def addItem(lst, item):
    i = bisect.bisect_left(lst, item)

    if i < len(lst)-1:
        if item != lst[i+1]:
            lst.insert(i+1, item)
    else:
        lst.insert(i+1, item)

    return lst



def extractTheRobotsFile(text):
    textList = text.splitlines()
    textList = [''.join(a.split()) for a in textList if a != '']
    textList = [a for a in textList if not a.startswith('#')]
    textList1 = [a.lower() for a in textList]
    robotsDictionary = {"delay": 1.5, "allowed": [], "forbidden": [] , "sitemap": "" }
    rulesStart = False
    agentBoxStart = False
    

    for index in range(len(textList)):
        item = textList[index]
        item1 = textList1[index]

        if not agentBoxStart:
            agentBoxStart = item1.startswith("user-agent:*") or item1.startswith("user-agent:dseuniprojectcrawler/1.0")

        if agentBoxStart & (rulesStart == False):
            if index != len(textList):
                if not textList1[index].startswith("user-agent"):
                    rulesStart = True

                    
        if agentBoxStart & rulesStart:
            indexOfColon = item.find(":")
            key = item1[0:indexOfColon]
            if key == "allow":
                addItem(robotsDictionary["allowed"], item[indexOfColon+1:])
            elif key == "disallow":
                addItem(robotsDictionary["forbidden"], item[indexOfColon+1:])
            elif key == "crawl-delay":
                robotsDictionary["delay"] = float(item[indexOfColon+1:])
            elif key == "sitemap":
                robotsDictionary["sitemap"] = item[indexOfColon+1:]
            elif key == "user-agent":
                agentBocStart = False
                rulesStart = False
            else:
                raise ValueError(f"Somehow the implemented rules are not sufficient, there is a word {key} at the beginning of the file")

    return robotsDictionary



# this function returns the url where the robots.txt file is located, if it exists
# according to RFC9309 (https://www.rfc-editor.org/rfc/rfc9309.html#name-locating-the-robots-txt-fil), this is 
# the case, if we leave the url before the 3rd "/" unchanged and simply add robots.txt to it
def robotsTxtUrl(url):
    counter = 0
    robotsUrl = ""
    for index in range(len(url)):
        if url[index] == '/':
            counter+=1
        if counter == 3:
            robotsUrl = url[0:index+1] + 'robots.txt'
            break
    return robotsUrl


#####################################
# The following functions detect if the crawler has been blocked by a domain
def crawlerBlocked()




    

# given a series utilises UEMA (Unbiased Exponential Moving Average, from Menth et al.: "On moving Averages, Histograms and Time- Dependent
# Rates for Online Measurement (https://atlas.cs.uni-tuebingen.de/~menth/papers/Menth17c.pdf))
# Note that cases t<t_0 and t <t_i < t_{i+1} are ignored for the calculation of S and N, since we only measure  (approximately) as
# soon as we have a new data point
def UTEMA(domain,value):
    t = time.perf_counter()
    beta = 1/1000000
    if domain not in responseTimes:
        # this will be the final weighted the average A after inclusion of the current data point
        A = 0
        # these are the Values for S and N in case t = t_0
        S = value
        N = 1 
        # --- measures time since a certain arbitrary point,at some moment somewhen before the start of the program
        # --- time is measured in seconds
        responseTimes[domain] = {"S_last":S, "N_last":N, "t_last": t }

   
    if responseTimes[domain] != None:
    # these are the cases t= t_i 
        S = responseTimes[domain]["S_last"]
        N = responseTimes[domain]["N_last"]
        t_last = responseTimes[domain]["t_last"]
        expWeight = math.exp(- beta *(t - t_last))

        S = expWeight * S + value
        N = expWeight * N + 1

    # updating the values in responseTime
    responseTimes[domain]["S_last"] = S
    responseTimes[domain]["t_last"] = t
    responseTimes[domain]["N_last"] = N

    # calculation of A 
    A = S / N

    return A



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



# this function is just for generating random Data in order to testplotResponses
def testData(a):
    # just part of the test if UTEMA works correctly
    # global randomDelays
    delayList = np.random.uniform(10**(-6),2* 10**(-6),10**6)
    valueList = np.random.exponential(a, 10**6)
    randomDelays = valueList

    dataPointsx = []
    dataPointsy = []



    
    responses = []

    for index in range(len(delayList)):
        responses.append([0,UTEMA("test", valueList[index])])
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
#testData(4)
#print(responseTimes["test"]["S_last"] / responseTimes["test"]["N_last"])
#randomDelays = np.array(randomDelays)
# print(np.mean(randomDelays))
           

    

# utilises U`tEMA (Unbiased Time- Exponential Moving Average, from Menth et al.: "On moving Averages, Histograms and Time- Dependent
# Rates for Online Measurement (https://atlas.cs.uni-tuebingen.de/~menth/papers/Menth17c.pdf))
def delayTime(delay):
    ''' calculates what the crawl- delay should be, i.e., the time, until the next 
    crawler is allowed to crawl the domain '''
    pass
    
    
def isTheCrawlerForSomeReasonBlocked()    
    

# this function does the following: 
# - first check if the url is english or not
# - check if thecurl is related to tübingen (in order to determine this, it can make sense to consider the incoming link)
# in order to do this, it might also be of importance to know if it is the subdomain of an already crawled url

def singleCrawler(url, IncomingLink):
    rules = extractTheRobotsFile(robotsTxtUrl(url))
    
    return []




