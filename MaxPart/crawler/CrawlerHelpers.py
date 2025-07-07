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
from UTEMA import UTEMA
from bs4 import BeautifulSoup
from heapdict import heapdict
import crawlerMetric
import threading
import duckdb
from pympler import asizeof


# in order to be able to raise customed- errors
class Error(Exception):
    pass
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




###############################################

###### some global variables ########

# informationFromInputForTheCrawler:
inputDict = {"crawlingAllowed": True}


# dictionary of discovered URLs which have not yet been crawled
# has entries of Form <url>: {urlDictionary},
# where urlDictionary has the 
# Fields:
#        - code: The status_code of the last try of a http- request for this url
#        - title: the title in the html- file, if the request was successfull
#        - text: the html file converted into human readable text by usage of BeautifulSoup
#        - lastRead: The time, measured in Unix- time when the url was read
#        - delay: the current crawl- delay
#        - outgoing: the list of pairs with entries that consist of one outgoing link 
# #          and its tueEng score, if it is already known, for each of the outgoing   
# #          links (refering to another url)
#        - incoming: the list of pairs with entries that consist of one incoming link
# #          and its tueEng score for each of the incoming links (refering to url)#   
#        - domainLinkingDept: This is the (currently) minimal number of links- chains of the same 
# #          domain 
#        - linkingDepth: This is the (currently) minimal number of link
#           chains of domains up to the domain of the currentURL
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


#dictionary of discovered urls not yet crawled, has entries of form:
# <url>:(<unix time from which on the url can be crawled>,{"delay": <delay>, "linkingDepth": "domainLinkingDepth": <integer>})
frontier = heapdict()

# contains entries of form <domain-name>: delay
# the delay is added to each individual delay in frontier if a new url is added and
# its domain matches one of the keys in this dictionary here
domainDelaysFrontier = {}

# contains entries of form <domain-name>:
robotsTxtInfos = {}


# for the checking-if blocked
   # resonseHttpCodes:
    #         fields: 
    #                - "domain": dictionary only exists, if it has at least 1 url- entry
    #                            to see, when there is an url- entry see description of field
    #                            "url" directly below 
    # ------------------------------------------                            
    # domain:
    #        fields: 
    #                - "delay": this delay is added to each of the calculated url- delays in 
    #                           the frontier whenever an url is newly inserted
    #                - "url": dictionary, this field only exists, if there was an error 
    #                         (status_code had form 3.xx, 4.xx, or 5.xx) for a http- request 
    #                         to this url, as this url was read from the frontier
    #                - "data": List of tuples (<time of http response>, <status_code>), stores
    #                          this for the last 100 requests
    #                - the 3 UTEMA- related and created fields: 
    #                          exist only after UTEMA(responseHttpErrorTracker, <weight>, domain) 
    #                          was called the first time, for details see UTEMA
    #-----------------------------------------
    # url:
    #        fields: 
    #                - ""counters": dictionary created by handleURL, has fields of form                            <status_code : <integer> which are used to count the number
    #                               of times a certain staus- code has been received for this url
    #                - "data": dictionary created by handleURL, information
    #                - all the UTEMA- related and created fields: 
    #                                 exist only after UTEMA(responseHttpErrorTracker, <weight>, domain) 
    #                                 was called the first time, for details see UTEMA
    
    #
    #   
responseHttpErrorTracker = {}



# these urls should get stored as soin as the len(cachedUrls) > 10^3 entries
cachedUrls = []


## blocked URLS- tracking:
## domains/ urls that are discontinued, structure: "domain":{ <domain>: "url": <url>}, as soon as  the url- entries of the full discontinued list are > 10^3 or the domain- entries > 10^3 store them
discontinued = {}



#this list contains pairs of (url,code), where code is an unknown status code these
# urls are taken off the frontier

######## cache for all the disallowed URLS, disallowed means: We suspect we have
# been blocked on the URL

disallowedURLCache = []

######## cache for all the disallowed domains, disallowed means: We suspect we have
# been blocked on the URL
disallowedDomainsCache = {}








##################################
# GENERAL HELPERS
################################ 
# The functions in this paragraph all are used in more than one of the following paragraphs
#----------------------------

#.....................................................................=
#testing done?: Not yet
#.....................................................................=



# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage is under development
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


# function that creates a filling for a full test of the
# frontier- responseHttp- pipeline
def testFill(number):
    #checking if frontier["url1"]
    pass
    

# Given a list of (relative) urls and a comparison url, which one is the 
# longest match?
def longestMatch(urlList, comparisonURL):
    maxMatch = 0
    for index in range(urlList):
        matchSize = 0
        size = min(len(urlList),len(comparisonURL))
        for a in range(size):
            if urlList[index]== comparisonURL[index]:
                    matchSize += 1
            else:
                 break
        if maxMatch < matchSize:
                maxMatch = matchSize
    return maxMatch


        
            
                
        



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


# this function returns the domain- string
# (www. ... until, not including "/" is reached (if it exists)), given a
# full (not a relative) url as a string
def getDomain(url):
    '''extracts the domain from a given url'''
     # this extracts the domain- name from the url
    domain = re.search("//[^/:]*", url).group()[2:]
    return domain
     
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    

# basic idea:   gets a url and a reason, depending on the reason
#               informations about url/ the domain of the url are #                deleted/ added
#               to different data structures. For details:
#               see the comments in the function body
#               
# usage:        used in handleCodes, handle3xx.Loop
# arguments:    
#               url: the url for which wee want the informations stored/ deleted
#               reason: is one of "success", "average", "counter", "loop"
# return value: 
#               -
# REQURIEMENT: url must be in url- frontier
def moveAndDel(url, reason):
    domain = getDomain(url)
    urlInFrontier = False
    
    # in the following we check if the required entry of the responseHttpErrorTracker does 
    # indeed exist 
    
    
    if url in frontier:
        urlInFrontier = True
            
    if reason == "average":
        try:
            data =  responseHttpErrorTracker[domain]["data"] 
        except KeyError as e:
            print("Somehow moveAndDel gets a url for which responseHttpErrorTracker[domain]['data']  does not exist")            
    if reason not in ["success", "loop"]:
        try:
            data =  responseHttpErrorTracker[domain][url]["data"] 
        except KeyError as e:
            print("Somehow moveAndDel gets a url for which responseHttpErrorTracker[domain][url]['data']  does not exist") 
    
        
     # in this case we check if at some point there 
     # was a failed http- request regarding this message
     # if there was, we delete the associated field 
     # from the responseHttpErrorTracker   
    if reason == "success":
        if domain in responseHttpErrorTracker:
            if url in domain:
                del responseHttpErrorTracker[url]
        if url in frontier:
            del frontier[url]
        
        
    # this is the case, when there have been "too many"
    # (according to the weighted average, see handleCodes and UTEMA)failed http- requests in a certain domain
    elif reason == "average":
        disallowedDomainsCache[domain] = {"average": reason, "data": copy.deepcopy(data)}
        del responseHttpErrorTracker[domain]
        for a in frontier:
            if domain in a:
                del frontier[a]
        
    # this is the case, when there have been too many
    # failed http- requests, with a certain status_code
    # , see handleCodes   
    elif reason == "counter":
        disallowedURLCache[domain][url]  = ({"reason": "counter", 
            "data": responseHttpErrorTracker[domain]["data"][-1:]})
        del responseHttpErrorTracker[domain][url]
        if url in frontier:
            del frontier[url]
        
    
    # this is the case, if there was a redirect- loop
    # detected, see handleCodes and handle3xxLoop
    elif reason == "loop":
        loopList = responseHttpErrorTracker[domain][url]["loopList"]
        disallowedURLCache[url]  = ({"reason": "loop", 
            "data":  [loopList[0]]})
        for a in loopList:
            if a[0] in frontier:
                del frontier[a]
        del responseHttpErrorTracker[domain][url]
    
    else:
         raise Exception(f''' the reason '{reason}' that was given to moveAndDel does not
                         exist''')
     
    
##################################
# DATABASE MANAGEMENT
################################ 
# This paragraph is all about the databases urlsDB, disallowedDomainsDB, and disallowedURLDB
# and about their management, and storing the cache into them after each of the caches has reached a certain size
#----------------------------

def putInStorage(list, tableName):
    for a in list:
        
    
#......................................
#all about urlsDB
#......................................

crawlerDB = duckdb.connect("urlsDB.duckdb")

# Create the database
crawlerDB.execute("""
    CREATE TABLE urlsDB (
        id TEXT,
        title TEXT,
        text TEXT,
        lastFetch DOUBLE,
        outgoing TEXT[],
        incoming TEXT[],
        domainLinkingDepth TINYINT,
        linkingDepth TINYINT,
        tueEngScore
""")


def storeCache():
    # thus value could be optimised, byt th
    if len(cachedUrls) > 20000:
        
        
        
        









# TODO: implement this get- method, which returns the information about the url
# as long as it is not in the disallowedURL Cache nor in the disallowedURL DataBase
# nor its domain is disallowed, further check if it is 
def getPageInfo(url):
    if url not in disallowedURLCache:
        #... then get the url 
        pass
      
      

# looks the stored information for the url up, either in cachedUrls, or in urlsDB
# finds the entry and returns it and deletes it
# TODO: IMPLEMENT
def  readAndDelUrlInfo(url):
    return None

# returns True, if the url is already in storage, either in cachedUrls or in urlsDB, otherwise returns false
def isUrlStored(url):
    return False

# checks if there is an entry for the url in the disallowedDomainsCach, in the
# disallowedURLCache, in the disallowedDomainsDB, or in the disallowedURLDB if this
# the case, then it returns True, otherwise it returns False
#TODO: IMPLEMENT
def findDisallowedUrl(url):
    return False

    

#.....................................................................=
#testing done?: Not yet
#.....................................................................=

##################################
# ROBOTS.TXT  
################################ 
# The functions in this paragraph all have to do with the robots.txt page
#----------------------------

#.....................................................................=
#testing done?: Some basic tests were done, but no systematic testing
#.....................................................................=


# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage is finished for now, the extractTheRobotsFile could be vastly shortened, by using 
# the regular expression library re
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


#............................
# helpers specifically for this task
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
    robotsTxtUrl = getDomain(url) + "/robots.txt"
    text = requests.get(robotsTxtUrl).text
    
    
    textList = text.splitlines()
    textList = [''.join(a.split()) for a in textList if a != '']
    textList = [a for a in textList if not a.startswith('#')]
    textList1 = [a.lower() for a in textList]
    robotsDictionary = {"delay": 0, "allowed": [], "forbidden": [] , "sitemap": "" }
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

def robotsTxtCheck(url):
    domain = getDomain(url)
    roboDict = {}
    value = (10, False)
    allowedMatch, forbiddendMatch = 0,0
    if domain in robotsTxtInfos:
        roboDict = robotsTxtInfos[domain]
        
    else:
        roboDict = extractTheRobotsFile(url)
        robotsTxtInfos[domain] = roboDict
    allowedMatch = longestMatch(roboDict["allowed"], url)
    forbiddenMatch = longestMatch(roboDict["forbidden", url])
    
    if allowedMatch > forbiddenMatch:
        value = (roboDict["crawl-delay"], True)
        
    return value
        
    
    




##################################
# HANDLING UNWANTED HTTP- RESPONSES
################################ 
# The functions in this paragraph all have to do with handling URL status codes of the form
# 3.xx, 4.xx, and 5.xx
#----------------------------

#.....................................................................=
#testing done?: No!
#.....................................................................=


# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage still needs work
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


# CURRENT WORKERS :::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# currently working on the passage: Nobody
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


#............................
# helpers specifically for this task
#............................

# used to read the retry-after header from response.get(<url>).headers
def retry(value):    
    if value :
        if value.isdigit():
            value = int(value)
            
        else:
            # first converts the time of the crawler and the time of the retry-value in the same zone, then converts it to seconds and then calculates
            # how many seconds the retry- date is in the future
            value = (parse(value).astimezone(timezone.utc)        
            .timestamp())                    
            
    return value



#####################

    
    
#####################
# multiplies the delay time by 2, bounded by 3600 s (1 hour)
def exponentialDelay(url, info):
    domain = getDomain(domain)
    frontier[url] = info
    delay = frontier[url][1]["delay"] 
    if delay > 3600:
        delay = 3600
    else:
        delay = delay*2

    frontier[url][1]["delay"] = delay
    frontier[url][0] += delay
    if frontier[url][0] < domainDelaysFrontier[domain]:
        frontier[url][0] = domainDelaysFrontier[domain]
        
          
    
        


#............................
# the main functions
#............................  


# basic idea:   detects if there are redirection loops
#               (if the last 5 http- responses, including the current one
#               where all 3.xx responses), if this is the case 
#               moveAndDel with reason="loop" is called
#               
# usage:        used in handleCodes
# arguments:    
#               url: the url for which we want to handle the response
#               headers: the headers fields of request(url).headers
#               code: the status code of request(url).headers
# return value: 
#               none



# detects if a URL is the fifth entry in a chain 
# of reroutes. If this is the case, all the URLs in the list get
# taken from the frontier and the first url of the list is disallowed
# REQUIREMENTS: location and url need to be absolute and not relative urls
def handle3xxLoop(url, location, code):
    time = time.time()
    domain = getDomain(url)
    newUrl = url
    values = [True, url]
    if 299< code or code > 400:
        return values

    if location:
        newUrl = location
        if "loopList" in responseHttpErrorTracker[domain][url]:
            loopList = responseHttpErrorTracker[domain][url]["loopList"]
            loopList.append((newUrl,code, time))
            values[1] = newUrl
            
            
            if len(loopList) == 5:
                moveAndDel(url, "loop")
                values[1] = False
            return values
    # use this case for the case that for some reason there is no Location in the http - resonse of url, even thoug its status_code is 3.xx
    else:
            responseHttpErrorTracker[domain][url]["loopList"]= [(url,code)]
            
    return values






# basic idea:   handles the possible different Status_codes of a url- request
#               
# usage:        used in frontierHandler
# arguments:    
#               url: the url for which we want to handle the response
#               headers: the headers fields of request(url).headers
#               code: the status code of request(url).headers
# return value: 
#               none
#more detail:
#------
#handles errors (htto- responses of the form 3.xx, 4.xx, 5.xx)
# error- treatment in detail:
#                           1. for some kinds of errors we want that after n calls of the url and n times getting the 
#                           same kind of error (we grouped some error- codes), we want to disallow it (put it into the 
#                           disallowedURLs, from where if this cache is full, if will be loaded into the disallowedURLsDB
#                           database and deleted from the responseHttpErrorTracker list as well as from the frontier

#                           2. We also track errors over a whole domain and weigh them, by calling UTEMA each time this function is called
#                              this way we update the UTEMA value for each received new error. If this value is > threshold (we chose 20 for now)
#                              the domain name is stored in the disallowedDomains cache and all urls of this domain are deleted from the responseHttpErrorTracker list
#                              as well as from the frontier
#
def handleCodes(url, code, location, info):
    domain = getDomain(url)
    values = (False, url)
    
 
    counter = responseHttpErrorTracker[domain][url]["counters"] [str(code)] 
    delay = frontier[url][1]["delay"]
        
    # now we just decide what happens at which code by case- distinction
    
    if 199 < code < 300:
        values[0] = True
        moveAndDel(url, "success")
        sample = 0
        
    
    if 299<code<400:
    # the reason we check this here, is for the simple purpose,
    # if the url - response has no Location header (should not be, but still)
        url, values[0] = handle3xxLoop(url,location, code)
        
        if (not values[0]):
            moveAndDel(url, "loop")
            sample = 1
        else:
            sample = 0
        
                  
        
    if code == 400:
        if counter == 3:
             moveAndDel(url, "counter")
            
        else:
            exponentialDelay(delay, url, info)
        
        sample = 1
        
        
    
    
    elif 400 < code < 500 and code != 429:
        if counter == 2:
               moveAndDel(url, "counter")
        else:
            exponentialDelay(delay, url, info)
            
        sample = 1
            
        
    elif code == 429: 
        exponentialDelay(delay, url, info)
        
        if counter == 10:
              moveAndDel(url, "counter")
        sample = 0.5
            
    elif 499 < code < 507 or code == 599:
        exponentialDelay(delay, url, info) 
        
        if counter == 5:
               moveAndDel(url, "counter")
            
        sample = 1
            
    elif 506 < code < 510:
        if counter == 3:
               moveAndDel(url, "counter")
            
        else:
            frontier[url] = info
            info[1]["delay"] = 3600
            info[0] = info[0] + 3600
            if domainDelaysFrontier[domain] > info[0]:
                info[0] = domainDelaysFrontier[domain]
            
        sample = 0.75
        
    else:
        if counter == 3:
              moveAndDel(url, "counter")
        sample = 0.3
    if url in responseHttpErrorTracker[domain]:
        
        # max UTEMA - average (weighted average) of bad requests we
        # accept = 0.15
        if (UTEMA(domain, sample, responseHttpErrorTracker) > 8 and responseHttpErrorTracker[domain]["N_last"] >= 20):
            # in this case, we disallow the whole domain
            moveAndDel(url, "average")
            
    return values          
           
    
##################################
# A SINGLE CRAWLER
################################ 
# The main function in this paragraph is a function that crawls a given
# website (ONLY one) and checks
#----------------------------

#.....................................................................=
#testing done?: No!
#.....................................................................=


# current state of this passage:::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# This passage still needs a lot of work
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


# CURRENT WORKERS :::::::::::::::::::::::::::::::::::::::::::::::::::::::;
# currently working on the passage: Max
#::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::


#............................
# helpers specifically for this task
#............................



#------------
# given the body of a html - page (i.e. the requests(url.text))
# for which we already checked that it receives meaningful text
# (not the text- body of an error- http - request),
# we extract all the urls we can find from this page
def extractURLs(text):
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
    
     return full_urls
 
 
#TODO: implement this, this should optimise the delays for domains
def delay(domain):
    pass
     
        
            
# TODO: Changed my mind about the purpose of this function
#       what it should do is described below, however, as of now
#       it does not do that!!!

# basic idea:   given an URL it calls the robots.txt
# usage:        used in extractTheRobotsFile
# arguments:    
#               lst: is a list of lexicographically ordererd items
#               item: is an item that is to be inserted into the list
# return value: 
#               lst of lexicographically ordered items

#              
# !!!!! this is the main function the crawler- function uses !!!!!
# what it does: given an URL, it calls the URL 
def statusCodesHandler(url, responseHeaders, info):
    code = responseHeaders["status_code"]
    location = responseHeaders.get("Location")
    # for the question if it makes sense to disallow a whole domain
    # we calculate an UTEMA- weighted average, that is what the sample- value is for
    sample = 0.25
    domain = getDomain(url)
    time = time.time()
    

    if domain not in responseHttpErrorTracker:
         responseHttpErrorTracker[domain] = {"data": []}
    if url not in responseHttpErrorTracker[domain]:
         responseHttpErrorTracker[domain][url] = {"counters": {}}
         # responseHttpErrorTracker[domain][url]["timeData"] = [time]
         
         
    # data for debugging in case that the reason for moveAndDel is "average"   
    responseHttpErrorTracker[domain]["data"] += [(time,code)]
    responseHttpErrorTracker[domain]["data"] = responseHttpErrorTracker[domain][-100:]     
         
         
    if str(code) not in responseHttpErrorTracker[domain][url]["counters"]:
        responseHttpErrorTracker[domain][url]["counters"] = {str(code): 0}
         
    responseHttpErrorTracker[domain][url]["counters"] [str(code)] +=1
    
    return handleCodes(url, code, location, info)
    
    
# this function updates the information of urls alrady either in the cached urls, or alternatively in urlDB
def updateInfo(url, parentUrl):
    domainParent = getDomain(parentUrl)
    domainUrl = getDomain(url)
    info = readAndDelUrlInfo(url)
    info_1 = copy.deepcopy(info)
    if (info == None):
        raise Error("the updateInfo function received a url which was not yet in the cache or the database")
    
    info["incoming"].append(parentUrl)
    info["domainLinkingDepth"] = min(frontier[parentUrl][1]["domainLinkingDepth"] + 1, info["domainLinkingDepth"])
    
    if domainParent != domainUrl:
        info["linkingDepth"] = min(frontier[parentUrl][1]["linkingDepth"] + 1, info["linkingDepth"])
    else:
        info["domainlinkingDepth"] = min(frontier[parentUrl][1]["domainlinkingDepth"] + 1, info["domainlinkingDepth"])
    
    # Here we maybe want to update the tueEngScore if
    # some of the latter instructins changed the info    
    if info != info_1:
        pass
    
# this is only called, if the url is already in the frontier
def updateFrontier(url, ancestorUrl):
    domain = getDomain(url)
    ancestorDomain = getDomain(ancestorUrl)
    
    if domain == ancestorDomain:
        frontier[url][1]["domainLinkingDepth"] = (min(frontier[ancestorUrl]
                                         [1]["domainLinkingDepth"]+1,frontier[url][1]["domainLinkingDepth"] ))
    else:
        frontier[url][1]["linkingDepth"] = (min(frontier[ancestorUrl]
                                         [1]["linkingDepth"]+1,frontier[url][1]
                                         ["linkingDepth"] ))
    frontier[url][1]["incomingLinks"].append(ancestorUrl)

    
    
    
    
    
    
    
# this function gets an url, reads all urls that are of interest to us and then checks for each of them if they
# are still admissible, i.e, if they have been disallowed or if they are already stored, in this case some of their
# information needs to be updated (happens via updateInfo). If this is not the case, it throws a list with entries of the form [<Unix time starting at which access to the url is allowed>, url, {"delay": <delay>, "linkingDepth": "domainLinkingDepth": <integer>, "incomingLinks": < list of parent- urls>}] into the frontier
#REQUIREMENTS: predURL must still be in the frontier at the time of call!!!!!
def frontierWrite(url, predURL):
    domain = getDomain(url)
    predDomain = getDomain(predURL)
    
    if url in frontier:
        updateFrontier(url, predURL) 
    elif findDisallowedUrl(url):
        pass
    elif isUrlStored(url):
        updateInfo(url, predURL)
    else:
        
        robotsCheck = robotsTxtCheck(url)
        if robotsCheck [1]:
            if domain in domainDelaysFrontier:
                domainDelaysFrontier[domain] = max(domainDelaysFrontier[domain],
                                               robotsCheck[0])
            else:
                domainDelaysFrontier[domain] = robotsCheck[0]
        
            frontier[url] = (0,{"delay": 0})
    
            if domain in domainDelaysFrontier:
                frontier[url][1]["delay"] = domainDelaysFrontier[domain]
                frontier[url][0] = time.time() + domainDelaysFrontier[domain]
        
            else:
                frontier[url][1]["delay"] = 0
                frontier[url][0] = time.time()
        
            if domain == predDomain:
                frontier[url][1] ["domainLinkingDepth"] = frontier[predURL][1]["domainLinkingDepth"]+1
                frontier[url][1]["linkingDepth"] = frontier[predURL][1] ["linkingDepth"]
            else:
                frontier[url]["linkingDepth"] = frontier[predURL] [1]["linkingDepth"]
                frontier[url]["domainLinkingDepth"] = frontier[predURL]["domainLinkingDepth"]
            frontier[url][1]["incomingLinks"].append(predURL)

    
  
    
    
    
# this is only called for urls which are neither in the caches nor in the
# databases, it reads the entry of the frontier with the smallest time to wait
# and creates the information for the storage for it, if the http- request #works out (if not the url is rescheduled via the handleCodes in 
# statusCodeHandler), or after too many rescheduling, just deleted, and 
# in some cases it even goes into the disalloweURLCache, or the domain 
# goes into the disallowedDomainsCache, for mor information see handleCodes). Further if the request works out, generated information is stored in cachedURLs
def frontierRead(info, url):
    wait = info[0]-time.time()
    if wait > 0:
        time.sleep(wait)
    
    response = requests.get(url)
    if response.headers["Retry-value"]:
        retry(response.headers["Retry-value"])
    url, valid = statusCodesHandler(url,response.headers, info)
    
    if not valid:
        return
    
    
    cachedUrls[url] =  {"title": "", "text": "","lastFetch": time.time(), "outgoing": [], "incoming": [],
                                       "domainLinkingDept":5, "linkingDepth": 50, "tueEngScore": 0.0}
        
    info = cachedUrls[url]
        
    rawHtml = response.text
    info[url]["title"] = searchText(rawHtml,"<title>", "</title>",[] ) 
    info["text"] = BeautifulSoup(rawHtml, "html.parser")
    info["lastFetch"] = time.time()
    info["incoming"] = info["incomingLinks"]
    info["linkingDept"] = info["linkingDepth"]
    info["domainLinkingDept"] = info["domainLinkingDepth"]
    info["tueEngScore"] = 1 
    info["outgoing"] = extractURLs(info["text"])
    
    if info["tueEngScore"] >0.5:
        for successorUrl in info["outgoing"]:
            frontierWrite(successorUrl,url)
    
    moveAndDel(url, "success")
    cachedUrls[url] = info
        
        
        
        
        
    
        
        
        
         

    

#................................
# the main functions
#................................
           

    

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
    if domain in disallowedDomainsCache:
        pass
        

def inputReaction():
    while True:
        cmd = input()
        
        if cmd == "stop":
            inputDict["crawlingAllowed"] = False
            

            
            print("the crawler now stores the frontier, load the caches into the databases and won't read from the frontier any more. Furthermore, after this is done, the crawler function call will end")
        
        if cmd == "newSeed":
            print('''The program waits for the path to the seed. It has to be of the a correct path, starting from the folder crawler ''')
            
     





input_thread = threading.Thread(target=inputReaction)
input_thread.start()




# this is the crawler function, it maintains the caches (puts them into storage)
# if necessary, and opens
def crawler():
    
    while len(inputDict["crawlingAllowed"]) != 0:
        for i in range(100):
          url, frontierInfo = frontier.popitem()
          frontierRead(frontierInfo, url)
    # TODO: implement storeEverything      
    # storeEverything()
    
    
    
    
    
    
    
    
    return []





# %%
