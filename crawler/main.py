
import databaseManagement



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



###### some global variables ########
# just needed to manage the interactions between the the main_thread running the crawler and the input_thread running
# the input
inputDict = {"crawlingAllowed": True, "running": True}




frontier = heapdict()
frontierDict = {}

# contains entries of form <domain-name>: delay
# the delay is added to each individual delay in frontier if a new url is added and
# its domain matches one of the keys in this dictionary here
domainDelaysFrontier = {}


# contains the UTEMA - averaged response times an the UTEMA- data per domain (for speed optimisation)
responseTimesPerDomain = {}


# here everything catched by the extractUrls function lands, that raises an error even in url- translation already
strangeUrls = []

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
cachedUrls = {}


######## cache for all the disallowed URLS, disallowed means: We suspect we have
# been blocked on the URL

disallowedURLCache = {}

######## cache for all the disallowed domains, disallowed means: We suspect we have
# been blocked on the URL
disallowedDomainsCache = {}





# for safe threading:
# lock is just for input_thread vs main_thread
lock1 = threading.Lock()


# trying to catch the input wihtout using locks
stopEvent = threading.Event()


def inputReaction():
    while not stopEvent.is_set():
        print("[debug] Waiting for input...")
        cmd = input()
        print("[debug] Received input:", cmd)
        print("[input] trying to acquire lock")
        print("[input] lock acquired")
        if cmd == "stop":
            print("[input] setting flags to stop")
            stopEvent.set()
            running = False
            print("the crawler now stores the frontier, load the caches into the databases and won't read from the frontier any more. Furthermore, after this is done, the crawler function call will end")
    
    
    
    
    
        
def printInfo():
    print(f"the actual number of cachedUrls: {len(cachedUrls)}")
    print(f"the actual number of tracked websites (because of http- statuscode): {len(responseHttpErrorTracker)}")
    print(f"the size of the frontier: {len(frontier)}")
    print(f"the actual number disallowedUrls: {len(disallowedURLCache)}")
    print(f"the actual number disallowedDomains: {len(disallowedDomainsCache)}")
    printNumberOfUrlsStored()
    for index in range(min(10, len(frontier)-1)):
                if frontier != []:
                    url = list(frontier)[-(index-1)]
                    if helpers.getDomain(url) in responseHttpErrorTracker:
                        print(f'''In the domain {helpers.getDomain(url)} these were the last status_codes at the times: {[a[1] for a in responseHttpErrorTracker[helpers.getDomain(url)]["data"]]}''')
                        print("--------------------------")
    print("---------------------------------------------------")
    
    
    # this is the crawler function, it maintains the caches (puts them into storage)
# if necessary, and opens
# gets the initial seed list as input
def crawler(lst):#inputThread):
    global frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, disallowedDomainsCache, cachedUrls, strangeUrls, responseHttpErrorTracker 
    # IMPORTANT: Activate this in order to load the earlier frontier from the database
    print("Input not yet available, please wait!")
    global inputDict
    frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, disallowedDomainsCache, cachedUrls, strangeUrls, responseHttpErrorTracker = load(frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, disallowedDomainsCache, cachedUrls, strangeUrls,
         responseHttpErrorTracker)
    frontierInit(lst)
    counter = 0
    threading.Thread(target=inputReaction, daemon=True).start()
    print("Did it run twice????")
    
    l = len(frontier)
    
    print("Initial l =", l)
    print("stopEvent.is_set() =", stopEvent.is_set())
    while l !=0 and not stopEvent.is_set():
        # IMPORTANT: Want to store the cachedURLs into the dabase, after a certain amount of entries are reached
        # (currently 20 000, which should be doable by every system with 4GB RAM (still usable during it,
        # takes accordig to chatGPT only 1 GB ram))
        if frontier.peekitem()[1] < time.time():
            storeCache(cachedUrls)
            lastCachedUrl = manageFrontierRead()
            counter +=1
            l = len(frontier) 
                
        if l == 0 or stopEvent.is_set():
            print(f"last storedUrl: {lastCachedUrl}")
            break
        if len(frontier)!= len(frontierDict):
            print(f"urls only contained in frontierDict, but not infrontier: {[a for a in frontierDict if a not in frontier]}")
            raise Error("the frontier does not have the same lengt as the frontierDict!")
        
    
        if counter % 10 == 0:
            counter = 0
            printInfo()

               
    stopEvent.set()  
    printInfo()
        
     # IMPORTANT: Activate this in order to store cachedUrls into the database, when the program stops
    storeCache(cachedUrls, forced = True)

    store(frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, disallowedDomainsCache, cachedUrls, strangeUrls,
         responseHttpErrorTracker)
    
   
    
    store(frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, disallowedDomainsCache, cachedUrls, strangeUrls,
         responseHttpErrorTracker)


def runCrawler(lst):
    if __name__ == "__main__":
        crawler(lst) #)
        closeCrawlerDB()
        
        
#%%
#this was for my own test purposes
#runCrawler(["rubbish"])
runCrawler(["https://www.bristol.ac.uk", "https://www.cbsnews.com", "https://www.newyorker.com","https://www.visitsingapore.com"])

#runCrawler(["https://whatsdavedoing.com"])

#runCrawler(csvToStringList("justCrawling/crawler/seedPages.csv"))

# print( crawlerDB.execute(f"SELECT MAX(linkingDepth) FROM urlsDB ").fetchone())
#print( crawlerDB.execute(f"SELECT MAX(domainLinkingDepth) FROM urlsDB ").fetchone())
# print( crawlerDB.execute(f"SELECT MAX(linkingDepth) FROM urlsDB ").fetchone())
# print(crawlerDB.execute(
#     "SELECT url, text FROM urlsDB WHERE url = ?",
#     ("https://tuenews.de/en/latest-news-english/",)
# ).fetchone())
# maybe useful for testing the http status_codes later on:
# https://the-internet.herokuapp.com/status_codes/200
