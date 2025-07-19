


#%%%%%%%%%%%%%%%%%%%%%%%%%%%
import random
import requests
from requests.adapters import HTTPAdapter
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
from heapdict import heapdict
import threading 
import duckdb
from pympler import asizeof
import html
from seed import Seed as seed
from exportCsv import export_to_csv as expCsv 
from parsingStuff import parseText as getText
from csvToListOfStings import csvToStringList
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from multiprocessing import Process
import queue
import sys
import os
import httpx
import asyncio
import warnings
from databaseManagement import (store, load, storeCache, findDisallowedUrl, readUrlInfo, printNumberOfUrlsStored 
     ,updateTableEntry, closeCrawlerDB)
import helpers

#####################
# multiplies the delay- time currently stored in frontierDict[url]["delay"] by 2, bounded by 3600 s (1 hour)
# input:
#       - url: an url
#       - info: frontierDict[url]
def exponentialDelay(url, info):
    '''increases the crawl- delay associated with that url exponentially'''
    domain = helpers.getDomain(url)
    
    if domain:
        # frontierDict[url] = info
        
        delay =frontierDict[url]["delay"] 
        if delay > 3600:
            delay = 3600
        else:
            delay = random.uniform(delay*2/1.4, delay*2)
            
        frontierDict[url]["delay"] = delay
        frontier[url] = time.time() + delay
        if domain in domainDelaysFrontier:
            if frontierDict[url]["delay"] < domainDelaysFrontier[domain]:
                frontier[url] = time.time() + domainDelaysFrontier[domain]
                frontierDict[url]["delay"] = domainDelaysFrontier[domain]
        
    
        
          
#input:
#        - location, code: see fetchSingleResponse in urlRequestManagement.py
#        - info: frontierDict[url]
#        - responseHttpErrorTracker: responseHttpErrorTracker
#        - retry: The retry- value as returned by retry from helpers.py 
# output: 
#        - [<Boolean>,newUrl], where the boolean is True if and only if the value of code was of form 2.xx
#          newUrl is a url, which might be different than url, in case a redirection happened (code was of form 3.xx)
def statusCodesHandler(url, location, code, info, responseHttpErrorTracker, retry):
    # for the question if it makes sense to disallow a whole domain
    # we calculate an UTEMA- weighted average, that is what the sample- value is for
    sample = 0.25
    domain = helpers.getDomain(url)

    time_ = time.time()
    
    # in order to see why it makes sense to handle this case this 
    # way one must realise, that the return value of statusCodesHandler is
    # handleCodes(url, code, location, info)
    if not domain:
        return [False, url]
    if domain not in responseHttpErrorTracker:
        responseHttpErrorTracker[domain] = {"data": [], "urlData":{}}
    if url not in responseHttpErrorTracker[domain]["urlData"]:
        responseHttpErrorTracker[domain]["urlData"][url] = {"counters": {}}
        # responseHttpErrorTracker[domain]["urlData"][url]["timeData"] = [time_]
        
        
    if code:    
        if str(code) not in responseHttpErrorTracker[domain]["urlData"][url]["counters"]:
            responseHttpErrorTracker[domain]["urlData"][url]["counters"] = {str(code): 0}
            
        responseHttpErrorTracker[domain]["urlData"][url]["counters"] [str(code)] +=1
        # data for debugging in case that the reason for moveAndDel is "average"   
        responseHttpErrorTracker[domain]["data"] += [(datetime.fromtimestamp(time_).isoformat(),code)]
        responseHttpErrorTracker[domain]["data"] = responseHttpErrorTracker[domain]["data"][-100:]     
    else:
        
        if "connection failed" not in responseHttpErrorTracker[domain]["urlData"][url]["counters"]:
            responseHttpErrorTracker[domain]["urlData"][url]["counters"] = {"connection failed": 0}
        else:
            responseHttpErrorTracker[domain]["urlData"][url]["counters"] ["connection failed"] +=1
        responseHttpErrorTracker[domain]["data"] += [(datetime.fromtimestamp(time_).isoformat(),"connection failed")]
        responseHttpErrorTracker[domain]["data"] = responseHttpErrorTracker[domain]["data"][-100:]    
            
        
    

    
    result = handleCodes(url, code, location, info)
    if retry:
        # if for whatever reason there was a retry- value received in the http- response (in fetchSingleResponse in urlRequestManagement)
        # we respect it, and thus need to re-schedule the url in the frontier accordingly
        frontier[url] = frontier[url]+ retry
    
    return result
    
        


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
    time_ = time.time()
    domain = helpers.getDomain(url)
    newUrl = url
    values = [True, url]
    
    if not domain:
        raise Error(f'''T {url}" has no recognizable domain,, but this should have been detected much 
                    earlier in the call hierarchy!''')
    
    # if 299< code or code > 400:
    #     return values

    if location:
        newUrl = location
        newDomain = helpers.getDomain(newUrl)
        values[1] = newUrl
        # if this is no domain, leave values[0] as True, the error will then be caught by readFrontier later on
        # after the urls has been being written back in the frontier, the http request will report none (if the domain was not valid,
        # the url also mustn't be)
        if newDomain:
            if "loopList" in responseHttpErrorTracker[newDomain][newUrl]:
                loopList = responseHttpErrorTracker[newDomain][url]["loopList"]
                loopList = responseHttpErrorTracker[domain]["urlData"][url]["loopList"].append((newUrl,code, time_))
                
                
                if len(loopList) == 5:
                    moveAndDel(url, "loop")
                    values[0] = False
                return values
    # use this case for the case that for some reason there is no Location in the http - response of url, even thoug its status_code is 3.xx
    else:
            responseHttpErrorTracker[domain]["urlData"][url]["loopList"]= [(url,code)]
            
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
#handles errors (http- responses of the form 3.xx, 4.xx, 5.xx)
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
    domain = helpers.getDomain(url)
    values = [False, url]
    
    if not domain:
        return values
    
    if code:
        counter = responseHttpErrorTracker[domain]["urlData"][url]["counters"] [str(code)] 
    else:
        counter = responseHttpErrorTracker[domain]["urlData"][url]["counters"] ["connection failed"]   
    # now we just decide what happens at which code by case- distinction
    if not code:
        sample = 1
        if counter == 3:
               moveAndDel(url, "counter")
        else:
            exponentialDelay(url, info)
    
    elif 199 < code < 300:
        values[0] = True
        #moveAndDel(url, "success")
        sample = 0
        
    
    elif 299<code<400:
    # the reason we check this here, is for the simple purpose,
    # if the url - response has no Location header (should not be, but still)
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("2-------not in frontier------")
        values[0], url = handle3xxLoop(url,location, code)
        
        if (not values[0]):
            moveAndDel(url, "loop")
            sample = 1
        else:
            sample = 0
                
        
    elif code == 400:
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("3-------not in frontier------")
        if counter == 3:
             moveAndDel(url, "counter")
            
        else:
            exponentialDelay(url, info)
        
        sample = 1
    
    elif 400 < code < 500 and code != 429:
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("4-------not in frontier------")
        if counter == 2:
               moveAndDel(url, "counter")
        else:
            exponentialDelay(url, info)
            
        sample = 1
            
        
    elif code == 429: 
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("5-------not in frontier------")
        exponentialDelay(url, info)
        
        if counter == 10:
              moveAndDel(url, "counter")
        sample = 0.5
            
    elif 499 < code < 507 or code == 599:
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("6-------not in frontier------")
        exponentialDelay(url, info) 
        
        if counter == 5:
               moveAndDel(url, "counter")
            
        sample = 1
            
    elif 506 < code < 510:
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("7-------not in frontier------")
        if counter == 3:
               moveAndDel(url, "counter")
            
        else:

            frontierDict[url] = info
            info["delay"] = 3600
            frontier[url] = frontier[url] + 3600
            if domainDelaysFrontier[domain]['delay'] > frontier[url]:
                frontier[url] = domainDelaysFrontier[domain]
                
        sample = 0.75
        
    else:
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("8-------not in frontier------")
        if counter == 3:
              moveAndDel(url, "counter")
        sample = 0.4
    if url in responseHttpErrorTracker[domain]:
        
        # max UTEMA - average (weighted average) of bad requests we
        # accept = 0.15
        if (UTEMA(domain, sample, responseHttpErrorTracker) > 8 and responseHttpErrorTracker[domain]["N_last"] >= 20):
            # in this case, we disallow the whole domain
            moveAndDel(url, "average")
            
    return values          
           