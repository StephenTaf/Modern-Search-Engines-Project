



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


warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
print(f"TOP-LEVEL EXECUTION: __name__={__name__}, thread={threading.current_thread().name}")

# in order to be able to raise customed- errors
class Error(Exception):
    pass
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%
###############################################
# only for testing


###############################################



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


            
                
        




     

##################################
# DATABASE MANAGEMENT
################################ 
# This paragraph is all about the databases urlsDB, disallowedDomainsDB, and disallowedURLDB
# and about their management, and storing the cache into them after each of the caches has reached a certain size
#----------------------------




    

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

# used to read the retry-after header from response.get(<url>).headers (see statusCodeHandler in statusCodeManagement.py)
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

    
    
# this function updates the information of urls in the cached urls or in storage
def updateInfo(url, parentUrl, info, score):
    from metric import metric
    # If there was indeed an entry for this url in cache or storage, 
    # this value will be turned to True, this value is the return- value 
    updated = False
    
    if not parentUrl:
        return False
    domainParent = helpers.getDomain(parentUrl)
    domainUrl = helpers.getDomain(url)
    info_1 = copy.deepcopy(info)
    
    # since we don't want anything to break here, and 
    # nothing happens if this function just does nothing (frontierWrite then just finishes
    # without doing anything as well)
    if not domainParent or not domainUrl:
        return True
    
    if info:
        # as we now know that info is not None, we can read out the one dictionary that is 
        # stored in its one field, the field with key "url"
        updated = True
        info["incoming"].append([parentUrl,score])
        
        if domainParent != domainUrl:
            try:
                info["linkingDepth"] = min(frontierDict[parentUrl]["linkingDepth"] + 1, info["linkingDepth"])
            
            except KeyError as e:
                print(f"There is a key error, the parentUlr was {parentUrl}:", e)
            
        else:
            try:
                info["domainLinkingDepth"] = min(frontierDict[parentUrl]["domainLinkingDepth"] + 1, info["domainLinkingDepth"])
                
            except KeyError as e:
                print(f"There is a key error, the parentUlr was {parentUrl}:", e)
    
        updateTableEntry('urlsDB', info, ["url", url])
        # Here we maybe want to update the tueEngScore if
        # some of the latter instructins changed the info    
        # we decided against doing this in the final version, since we did not re-use the tueEungScore in the end
        # if info != info_1:
        #     info["tueEngScore"] = metric(info, url)
        # cachedUrls[url] = info
    return updated

        

#................................
# the main functions
#................................
           

    

# utilises UTEMA (Unbiased Time- Exponential Moving Average, from Menth et al.: "On moving Averages, Histograms and Time- Dependent
# Rates for Online Measurement (https://atlas.cs.uni-tuebingen.de/~menth/papers/Menth17c.pdf))
def delayTime(delay):
    ''' calculates what the crawl- delay should be, i.e., the time, until the next 
    crawler is allowed to crawl the domain '''
    pass
    




        
        
    


