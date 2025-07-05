#%%%%%%%%%%%%%%%%%%%%%%%%%%%
import requests
import bisect #module for binary search
import time
import matplotlib.pyplot as plt
import numpy as np
import math
import copy
import re
from datetime import datetime, timezone
from dateutil.parser import parse
from urllib.parse import urljoin, urlparse
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%
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



# FOR FARHA:


###############################################

###### some global variables ########



# dictionary used for the 
responseTimes = {}


# dictionary of discovered URLs which have not yet been crawled
# has entries of Form <url>: {urlDictionary},
# where urlDictionary has the 
# Fields:
#        - code: The status_code of the last try of a http- request for this url
#        - title: the title in the html- file, if the request was successfull
#        - text: The text in the body of the html- file
#        - scheduled: The time, measured in Unix- time when the next call of the url
#          will be allowed
#        - delay: the current crawl- delay
#        - outgoing: the list of pairs with entries that consist of one outgoing link #          and its tueEng score, if it is already known, for each of the outgoing   #          links (refering to another url)
#        - incoming: the list of pairs with entries that consist of one incoming link #          and its tueEng score for each of the incoming links (refering to url)#   
#        - linkingDepth: This is the (currently) minimal number of links of the same #          domain on which a website has been reached
#  
#        - tueEngScore: the score that determines, how relevant this page is to
#          Tübingen
#           and if it is in english, this is where the metric- function from    
#           crawlerMetric.py writes its entries, or if it updates the score (if we want
#           to implement that), where the score is updated; we initialise the
#           tueEngScore with a low number != 0 (and not so low, that multiplication 
#           with it will result in 0 due to computation error)
# {"code": 0, "title": "", "text": "","scheduled": time.time(), "delay": 1.5, "outgoing": [], "incoming": [],"linkingDepth":5 "tueEngScore: 0.1"}




urlFrontier = {}

#active redirection- paths, each entry is a list where a url follows
# another url, if there was a direct redirect to it
redirects = []


# for the checking-if blocked
## this dictionary has the simple form <domain>: {<code>: [<time of response]}
responseHttpCodes = {}



## we don't allow the crawler to access them, as soon as len(discontinuedDomains)>1000
# we store them
discontinuedDomains = {}


# these urls should get stored as soin as the len(cachedUrls) > 10^3 entries
cachedUrls = []


## blocked URLS- tracking:
## domains/ urls that are discontinued, structure: "domain":{ <domain>: "url": <url>}, as soon as  the url- entries of the full discontinued list are > 10^3 or the domain- entries > 10^3 store them
discontinued = {}


#disallowed urls: urls where we are actually forbidden access to according to the robots.txt
disallowed = {}


#this list contains pairs of (url,code), where code is an unknown status code these
# urls are taken off the frontier





##################################
# GENERAL HELPERS
################################ 
# The functions in this paragraph all are used in more than one of the following paragraphs
#----------------------------

#======================================================================
#testing done?: Not yet
#======================================================================



# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage is under development
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

# note, that this does much more than just receiving a regular expression, it gives a start-string (start) and 
# an end- string (end) everything in between is returned, without the entries in the list of strings (without)
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%




# basic idea:   Given a text, and a start- and end- string, as well as a list of without- strings
#               returns the text where exactly the strings of the form of items in without are deleted
#              string string string [string]
def searchText (text, start, end, without):
    inBetween = "("
    
    for index in range(len(without)):
        if index < len(without)-1:
            inBetween = inBetween + without[index] + "|"
            
        else:
            inBetween = inBetween + without[index] + ")"
            
    
    snippet = re.search(start + ".*" + end, text).group()
    snippet = re.sub(inBetween, "", snippet)
    
        #  string
    return snippet
    
# print(searchText("Hallo das ist ein Fehler toll","Hallo", "toll", [" Feh", "ler ", "ein", ""]))

# TODO: implement this get- method, which returns the information about the url
# as long as it is not in the disallowedURL Cache nor in the disallowedURL DataBase
# nor its domain is disallowed, further check if it is 
def getPageInfo(url):
    if url not in disallowedURLCache:
        #... then get the url 
        pass
      
    
    

# This function is still under development and not yet usable
def loadURL(url):
    try:
        response = requests.get(url)
        content = response.content
        
        if url not in urlFrontier and getPageInfo(url)["allowed"]:
            urlFrontier[url] = {"code": 0, "title": "", "text": "","scheduled": time.time(), "delay": 1.5, "outgoing": [], "incoming": [],"linkingDepth":5,"tueEngScore": 0.1}
        
        if 199 < response.status_code < 300:
            pass
    except: pass
    
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    
        

####### just for the testing of UTEMA (you find it below in this file):

randomDelays = []

######## cache for all the disallowed URLS, disallowed means: We suspect we have
# been blocked on the URL

disallowedURLCache = []

######## cache for all the disallowed domains, disallowed means: We suspect we have
# been blocked on the URL
disallowedDomainsCache = {}


def getDomain(url):
    '''extracts the domain from a given url'''
     # this extracts the domain- name from the url
    domain = re.search("//[^/:]*", url).group()[2:]
    return domain
     


##################################
# ROBOTS.TXT  
################################ 
# The functions in this paragraph all have to do with the robots.txt page
#----------------------------

#======================================================================
#testing done?: Some basic tests were done, but no systematic testing
#======================================================================


# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage is finished for now, the extractTheRobotsFile could be vastly shortened, by using 
# the regular expression library re
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


#............................
# helpers
#............................



# basic idea:   adds a new item to an already lexicographically ordered list
# usage:        used in extractTheRobotsFile
# arguments:    
#               lst: is a list of lexicographically ordererd items
#               item: is an item that is to be inserted into the list
# return value: 
#               list of lexicographically ordered items
def addItem(lst, item):
    i = bisect.bisect_left(lst, item)

    if i < len(lst)-1:
        if item != lst[i+1]:
            lst.insert(i+1, item)
    else:
        lst.insert(i+1, item)

    return lst



# basic idea:   loads the robots.txt
# usage:        used in extractTheRobotsFile
# arguments:    
#               lst: is a list of lexicographically ordererd items
#               item: is an item that is to be inserted into the list
# return value: 
#               lst of lexicographically ordered items
# []->
def extractTheRobotsFile(url):
    robotsTxtUrl = re.search(r"(http|https)://[^/]*", url).group() + "/robots.txt"
    text = requests.get(robotsTxtUrl).text
    
    
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





##################
#helpers of helpers -------------
# used to read the retry-after header from response.get(<url>).headers
def retry(headers):
    value = headers["retry-after"]
    
    if value != None:
        if value.isdigit():
            value = int(value)
            
        else:
            # first converts the time of the crawler and the time of the retry-value in the same zone, then converts it to seconds and then calculates
            # how many seconds the retry- date is in the future
            value = (parse(retry)
            .astimezone(timezone.utc)        
            .timestamp()                    
            - datetime.now(timezone.utc).timestamp())
    return value



#####################
# another small helper: is used  to move a domain from responseHttpCodes to dicontinuedDomains and delete it from the url frontier
#  discontinuedDomains[domain] = copy.deepcopy(responseHttpCodes[domain])
def moveAndDel(url, reason):
    domain = getDomain(url)
    
    # in the following we check if the required entry of the responseHttpCode does 
    # indeed exist
    if reason == "average":
        try:
            data =  responseHttpCodes[domain]["data"] 
        except KeyError as e:
            print("Somehow moveAndDel gets a url for which responseHttpCodes[domain]['data']  does not exist")            
    else:
        try:
            data =  responseHttpCodes[domain][url]["data"] 
        except KeyError as e:
            print("Somehow moveAndDel gets a url for which responseHttpCodes[domain][url]['data']  does not exist") 
    
        
    if reason == "average":
        discontinued[domain] = {"average": reason, "data": copy.deepcopy(data)}
        del responseHttpCodes[domain]
        
        
    elif reason == "counter":
        discontinued[domain][url]  = ({"reason": "counter", 
            "data": copy.deepcopy(data)})
        del responseHttpCodes[domain][url]
    
    elif reason == "loop":
        discontinued[domain][url]  = ({"reason": "loop", 
            "data": copy.deepcopy()})
        del responseHttpCodes[domain][url]
       
    else:
         discontinued[domain][url] =  ({"reason": "unknown StatusCode", 
            "data": copy.deepcopy(data)})
         del responseHttpCodes[domain][url]
        
    
    
    
   
            
    # the reason- fields value either "average" or "counter"
    # depending on the reason, why the domain was discontinued
    discontinuedDomains[domain]["reason"] = reason
    del urlFrontier[domain]
    del responseHttpCodes[domain]
    
    
#####################
# multiplies the delay time by 2, bounded by 3600 s (1 hour)
def exponentialDelay(delay, url):
    domain = getDomain(domain)
    d= delay
    if delay > 3600:
        d = 3600
    else:
        d = delay*2
    
    urlFrontier[domain][url]["crawl-delay"] += d
    
        


    

# given a series utilises UEMA (Unbiased Exponential Moving Average, from Menth et al.: "On moving Averages, Histograms and Time- Dependent
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
    dataPointsx = []
    dataPointsy = []



    
    responses = []

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


def handle3xxLoop(url, headers, delay, code):
    domain = getDomain(url)
    retry_delay = headers.get(retry(headers))
    if 299> code or code < 400:
        return url

    if "Location" in headers:
        newUrl = headers.get("Location")
        if "loopList" in responseHttpCodes:
            loopList = responseHttpCodes[domain][url]["loopList"]
            loopList.append((newUrl,code))
            
            
            if len(loopList) > 5:
                responseHttpCodes[domain][newUrl]["loopList"]["data"] = [("loop",loopList)]
                moveAndDel(url, "loop")
                return url
        else:
            responseHttpCodes["loopList"]= [(url,code)]
            
    return url


def handle5xxOr4xx(url, code, retry_delay, delay):
    domain = getDomain(url)
    counter = responseHttpCodes[domain][url]["counters"] [str(code)] 
    if urlFrontier[domain]["crawl-delay"] > urlFrontier[domain][url]["crawl-delay"]:
        delay = urlFrontier[domain]["crawl-delay"]
    else:
        delay = urlFrontier[domain][url]["crawl-delay"]
        
    # now we just decide what happens at which code by case- distinction
    
    
    
    if 299<code<400:
    # the reason we check this here, is for the simple purpose,
    # if the url - response has no Location header (should not be, but still)
        if counter == 4:
            moveAndDel(url, "counter")
        else:
            exponentialDelay(delay, url)
            
        sample = 0.2
        
                  
        
    if code == 400:
        if counter == 3:
             moveAndDel(url, "counter")
            
        else:
            exponentialDelay(delay, url)
        
        sample = 1
        
        
    
    
    elif 400 < code < 500 and code != 429:
        if counter == 2:
               moveAndDel(url, "counter")
        else:
            exponentialDelay(delay, url)
            
        
    elif code == 429: 
        if (retry_delay != None):
            urlFrontier[domain]["crawl-delay"] == retry_delay
            
        else:
            exponentialDelay(delay, url)
        
        if counter == 10:
              moveAndDel(url, "counter")
        sample = 0.5
            
    elif 499 < code < 507 or code == 599:
        if code == 503 and retry_delay != None:
            urlFrontier[domain]["crawl-delay"] == retry_delay
            
        else:
            exponentialDelay(delay, url) 
        
        if counter == 5:
               moveAndDel(url, "counter")
            
        sample = 1
            
    elif 506 < code < 510:
        if counter == 3:
               moveAndDel(url, "counter")
            
        else:
            urlFrontier[domain][url]["crawl-delay"] = 3600
            
        sample = 0.75
        
    else:
        if counter == 3:
              moveAndDel(url, "counter")
        sample = 0.3
    if url in responseHttpCodes[domain]:
        
        # max UTEMA - average (weighted average) of bad requests we
        # accept = 0.15
        if (UTEMA(domain, sample, responseHttpCodes) > 8 and responseHttpCodes[domain]["N_last"] >= 20):
            # in this case, we disallow the whole domain
            moveAndDel(url, "average")
            
           
    
            
        
            
             

def handleURL(url, responseHeaders, delay):
    code = responseHeaders["status_code"]
    # for the question if it makes sense to disallow a whole domain
    # we calculate an UTEMA- weighted average, that is what the sample- value is for
    sample = 0.25
    domain = getDomain(url)
    time = time.time()
    
    # ToDo: Change Value (use delay- function!)
    retry_delay = retry(responseHeaders)
    

    if domain not in responseHttpCodes:
         responseHttpCodes[domain] = {"data": []}
    if url not in responseHttpCodes[domain]:
         responseHttpCodes[domain][url] = {"counters": {}}
         responseHttpCodes[domain][url]["timeData"] = [time]
         
         
    # data for debugging in case that the reason for moveAndDel is "average"   
    responseHttpCodes[domain]["data"] += [(time,code)]
    responseHttpCodes[domain]["data"] = responseHttpCodes[domain][-100:]
    data = responseHttpCodes[domain]["data"]
         
         
         
         
    if str(code) not in responseHttpCodes[domain][url]["counters"]:
        responseHttpCodes[domain][url]["counters"] = {str(code): 0}
         
    responseHttpCodes[domain][url]["counters"] [str(code)] +=1
    
    if 399<code<600:
        handle5xxOr4xx(url, code, retry_delay, delay)
    elif 299<code<400:
       # handle3xx(url, code, delay, retry_)
       pass
    else:
        pass
        
         


           

    

# utilises UTEMA (Unbiased Time- Exponential Moving Average, from Menth et al.: "On moving Averages, Histograms and Time- Dependent
# Rates for Online Measurement (https://atlas.cs.uni-tuebingen.de/~menth/papers/Menth17c.pdf))
def delayTime(delay):
    ''' calculates what the crawl- delay should be, i.e., the time, until the next 
    crawler is allowed to crawl the domain '''
    pass
    
###########################
# filter the kind of urls we are interested in

    
 
 
def isUrlAllowed(url):
    domain = getDomain(url)
    if domain in discontinuedDomains:
        pass
        
        
# Given a list of (relative) urls and a comparison url, which one is the 
# longest match?
def longestMatch(urlList, comparisonURL):
        matchLenghts = []
        for index in range(urlList):
            matchSize = 0
            size = min(len(urlList),len(comparisonURL))
            for a in size:
                pass
        
                
                
            
    


#------------
def extractURLs(url):
     response = requests(url)
     html = response.txt
     
     url = "https://www.yale.edu"
     
     # this extracts the domain- name from the url
     domain = re.search("//[^/:]*", url).group()[2:]
     
     
     # for testing
     s = " <a href = 'dsdjshklfsl' </a>"
     
     urls = re.findall(r'''<a\s*href\s*= [ ]*("\').*("\')[ ]*>.*</a>''', html)
     urls = [re.search(r'''("|')[^ ]*("|')''', a).group()[1:-1] for a in urls]
     full_urls = [urljoin(url, a) for a in urls]
     
     
     # TODO: This does not work yet! If we extract the robotsTxtUrl we will, with high
     # probability get relative URLS -> no URL will be delete
     urls = [a for a in full_urls if a not in extractTheRobotsFile(robotsTxtUrl(url))["forbidden"]]
     urls = [a for a in full_urls if a not in discontinued]
    
     pass
     
     
     

    


# this function does the following: 
# - first check if the url is english or not
# - check if the url is related to tübingen (in order to determine this, it can make sense to consider the incoming link)
# in order to do this, it might also be of importance to know if it is the subdomain of an already crawled url


def singleCrawler(url, IncomingLink):
    rules = extractTheRobotsFile(robotsTxtUrl(url))
    
    
    
    
    
    
    return []





# %%
