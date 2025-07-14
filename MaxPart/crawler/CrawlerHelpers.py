



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
import json
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


warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
print(f"TOP-LEVEL EXECUTION: __name__={__name__}, thread={threading.current_thread().name}")

# in order to be able to raise customed- errors
class Error(Exception):
    pass
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%
###############################################
# only for testing
headers = ({ 
    "User-Agent": "MaxCrawler",
    #DSEUniProjectCrawler/1.0 (contact: poncho.prime-3y@icloud.com)", 
    #We don't have a webpage for our crawler
    "From": "poncho.prime-3y@icloud.com",
    # the different formats our crawler accepts and the preferences
    "Accept": "text/html,application/xhtml+xml q= 0.9,application/xml;q=0.8,*/*;q=0.7",
    # the languages our crawler accepts
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    #keeping the connection alive, so we do not need a new TCP handshake for each request
    "Connection": "keep-alive"})



###############################################

###### some global variables ########
# just needed to manage the interactions between the the main_thread running the crawler and the input_thread running
# the input
inputDict = {"crawlingAllowed": True, "running": True}



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
# <url>:(<unix time from which on the url can be crawled>,{"delay": <delay>, "linkingDepth": "domainLinkingDepth": <integer>, "incomingLinks": <List of incoming links>})
frontier = heapdict()

# needed since the heapdict structure only allows tuples -> immutable type
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


## blocked URLS- tracking:
## domains/ urls that are discontinued, structure: "domain":{ <domain>: "url": <url>}, as soon as  the url- entries of the full discontinued list are > 10^3 or the domain- entries > 10^3 store them
discontinued = {}


# this stores all urls where the request was unsuccessfull (such where there was no http- response )
noResponseAtAll = []



#this list contains pairs of (url,code), where code is an unknown status code these
# urls are taken off the frontier

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

siteMapPatterns = [
    r"sitemap.*\.xml$",       # sitemap.xml, sitemap-1.xml, sitemap_news.xml
    r"/sitemap/?$",           # /sitemap or /sitemap/
    r"sitemap_index.*\.xml$", # sitemap_index.xml
]

# we really don't want to crawl sitemaps, because if we do we might loose the actual structure of the website,
# which we will use for our scoring system
def isSitemapUrl(url: str) -> bool:
    url = url.lower()
    return any(re.search(p, url) for p in siteMapPatterns)

        
    
    

# Given a list of (relative) urls and a comparison url, which one is the 
# longest match?
def longestMatch(urlList, comparisonURL):
    maxMatch = 0
    for index in range(len(urlList)):
        matchSize = 0
        size = min(len(urlList[index]),len(comparisonURL))
        for a in range(size):
            if urlList[index][a] == comparisonURL[a]:
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
    inBetween = ""
    if len(without)>0:
        inBetween = "("
        
        for index in range(len(without)):
            if index < len(without)-1:
                inBetween = inBetween + without[index] + "|"
                
            else:
                inBetween = inBetween + without[index] + ")"
                
    snippet = re.findall(start + "(.*?)" + end, text)
    if len(snippet)!=0:
        snippet = re.sub(inBetween, "", snippet[0])
    else:
        snippet = ""
    return snippet
    
# print(searchText("Hallo das ist ein Fehler toll","Hallo", "toll", [" Feh", "ler ", "ein", ""]))


# this function returns the domain- string
# (www. ... until, not including "/" is reached (if it exists)), given a
# full (not a relative) url as a string
def getDomain(url):
    '''extracts the domain from a given url'''
     # this extracts the domain- name from the url
    domain = re.findall("//([^/:]+)", url)
    if len(domain)<1:
        #f"This is not a domain. The url before was: {url}")
        strangeUrls.append(url)
        return None
        
    return domain[0]
     
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
    
    if not domain:
        return
 

    
    # in the following we check if the required entry of the responseHttpErrorTracker does 
    # indeed exist 
    
    if url in frontier:
        urlInFrontier = True
            
    if reason == "average":
        try:
            data =  responseHttpErrorTracker[domain]["data"] 
        except KeyError as e:
            print("Somehow moveAndDel gets a url for which responseHttpErrorTracker[domain]['data']  does not exist")            
        
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
            del frontierDict[url]
        
        
    # this is the case, when there have been "too many"
    # (according to the weighted average, see handleCodes and UTEMA)failed http- requests in a certain domain
    elif reason == "average":
        disallowedDomainsCache[domain] = {"data": copy.deepcopy(data), "received": str(time.ctime())}
        del responseHttpErrorTracker[domain]
        for a in frontier:
            if domain in a:
                del frontier[a]
                del frontierDict[a]
        
    # this is the case, when there have been too many
    # failed http- requests, with a certain status_code
    # , see handleCodes   
    elif reason == "counter":
        disallowedURLCache  = {"reason": "counter", 
            "data": copy.deepcopy(responseHttpErrorTracker[domain]["data"] [-1]), "received": time.ctime()}
        del responseHttpErrorTracker[domain]["urlData"][url]
        if url in frontier:
            del frontier[url]
            del frontierDict[url]
        
    
    # this is the case, if there was a redirect- loop
    # detected, see handleCodes and handle3xxLoop
    elif reason == "loop":
        loopList = responseHttpErrorTracker[domain]["urlData"][url]["loopList"]
        disallowedURLCache[url]  = ({"reason": "loop", 
            "data":  [loopList[0]], "received": time.ctime()})
        for a in loopList:
            if a[0] in frontier:
                del frontier[a]
                del frontierDict[a]
        del responseHttpErrorTracker[domain]["urlData"][url]
    
    else:
        raise Exception(f''' the reason '{reason}' that was given to moveAndDel does not
                        exist''')
    

# in order to catch if there is no http- response received for a http- request to a given url  
def getHttp(url, headers = headers, allow_redirects=False,timeout=5):
    try:
        response = requests.get(url, timeout=timeout)
        response.encoding = 'utf-8' 
        return response  # HTTP response was received (any status)
    except requests.RequestException:
        return None  
##################################
# DATABASE MANAGEMENT
################################ 
# This paragraph is all about the databases urlsDB, disallowedDomainsDB, and disallowedURLDB
# and about their management, and storing the cache into them after each of the caches has reached a certain size
#----------------------------


def getLastStoredId(table):
      result = crawlerDB.execute(f"SELECT MAX(id) FROM {table}").fetchone()
      last_id = result[0] if result[0] is not None else 0
      
      return last_id
  
# this stores the given structure into a given table, note that for this to work 
# the structure must have entries of the form <field>: <list of fields>
# pack is a list of strings, and specifies which columns need to be json.dumps()-ed, in order to
# correctly store the given information
# disallowedColumns is a list of strings of columns I want to ignore during storing
# delete is True, if the table content should be deleted before 
# storing the new content, and false, if it shouldn't
def storeInTable(structure, tableName, field, pack =[], disallowedColumns =[], delete = False):
    id = getLastStoredId(tableName)+1
    if delete:
        
        crawlerDB.execute(f"DELETE FROM {tableName} ")
    data = []
    if not structure:
        return
    if structure == domainDelaysFrontier:
        columnNames = ["delay"]
    else:
        columnNames = list(structure[next(iter(structure))])
    # print("the column names", columnNames)
    questionMarks = "(" + "?, " * (len(columnNames)+2-1) + "?)"
    columnNames = ", ".join(columnNames)
    columnNames = f"id, {field}, " + columnNames
    
    if structure == domainDelaysFrontier:
        data = [tuple( [id+i, field] +[domainDelay])  for i,(field,domainDelay ) in enumerate(domainDelaysFrontier.items())]
        
        
    else:
        dictHelper = {}
        # for url in structure:
        #     dictHelper[url]= [id]
        #     dictHelper[url].append(url)
        #     for name in structure[url]:
        #         dictHelper[url].append(structure[url][name])
        # #     id +=1
        # for domain, entry in responseHttpErrorTracker.items():
        #     for item in entry.get('data', []):
        #         try:
        #             json.dumps(item)
        #         except TypeError as e:
        #             print(f"⚠️ Serialization error in domain={domain}: {item} ({type(item)})")
        #             raise
                
        dictHelper = {
                    field: [id+i, field] + [json.dumps(structure[field][a]) if (a in pack) else structure[field][a]  for a in  content.keys()]
                    for i, (field, content) in enumerate(structure.items())
    }
                #print("length of one of the entries:", len( dictHelper[url]))
                # if len( dictHelper[url])== 6:
                #     print(list(structure[url]))
                    
                    
        data = [tuple(dictHelper[url]) for url in dictHelper] 


    crawlerDB.executemany(
        f"INSERT INTO {tableName} ({columnNames}) VALUES {questionMarks}", data)
    crawlerDB.commit()
#     except:
#          raise Error(f'''storeInTable failed and the input was: {questionMarks},{columnNames}, now the data: {"------------------------------------------------- ".join([str(a) for a in data[0]])}_''')

# reads the the specified columns (is a String!) fromt table and 
# then stores them as a nested 1- level dictionary, such that
# structure the has entrie of form <field>: <dictionary the stores the
# information of one row of the table, such that the fields are the columns, except the column field
# note that in order for this to work field: must be the name of one of the columns
# further note that unpacks is a list of column- names (strings) whose entries where json.dumps() - coded
# they need therefore to be json.loads()- treated, note ttat again, each entry of unpacks must also be named in columns
def readTable(structure, table, columns, field, unpacks = []):
    rows = crawlerDB.execute(f"""SELECT {columns} FROM {table}""").fetchall()
    columns = [desc[0] for desc in crawlerDB.description]
    dictList = [dict(zip(columns, row)) for row in rows]
    for item in dictList:
        for name in item:
            # note that frontier neads special treatment, simply because its not a normal dictionary, but a heapdict, meaning it cannot store further structures directly in its fields            
            if len(item) > 2:
                structure[item[field]] = {}
                if name != field:
                    structure[item[field]][name] = item[name]
                for name in unpacks:
                    structure[item[field]][name] = json.loads(item[name] )
            else: 
                if name!= field:
                    structure[item[field]] = item[name]    
    crawlerDB.commit()
    crawlerDB.execute("VACUUM")
    crawlerDB.commit()
        
        
        
    
#......................................
#all about urlsDB
#......................................
crawlerDB = duckdb.connect("crawlerDB.duckdb")

#Create the tables, if they don't already exist
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS urlsDB (
        id BIGINT PRIMARY KEY,
        url TEXT,
        title TEXT,
        text TEXT,
        lastFetch DOUBLE,
        outgoing TEXT[],
        incoming TEXT,
        domainLinkingDepth TINYINT,
        linkingDepth TINYINT,
        tueEngScore DOUBLE)
    """)


crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS frontier (
        id BIGINT PRIMARY KEY,
        schedule DOUBLE,
        delay DOUBLE,
        url TEXT,
        incomingLinks TEXT,
        domainLinkingDepth TINYINT,
        linkingDepth TINYINT)
    """)


crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS strangeUrls (
        id BIGINT PRIMARY KEY,
        url TEXT,
        received TEXT)
    """)

crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS disallowedUrls (
        id BIGINT PRIMARY KEY,
        url TEXT,
        reason TEXT,
        received TEXT)
    """)


crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS disallowedDomains (
        id BIGINT PRIMARY KEY,
        domain TEXT,
        received TEXT,
        data TEXT)
    """)

# this table is for storage only and not to be intended to be read out for anything else
# than loading the errorss into responseHttpErrorTracker
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS errorStorage (
        id BIGINT PRIMARY KEY,
        domain TEXT,
        data TEXT,
        urlData TEXT)
    """)

crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS domainDelays (
        id BIGINT PRIMARY KEY,
        domain TEXT,
        delay DOUBLE)
    """)  

        
def storeFrontier(): 
        for url in frontier:
            frontierDict[url]["schedule"] = frontier[url]
        storeInTable(frontierDict, 'frontier', 'url',pack = ["incomingLinks"], delete= True )
        storeInTable(domainDelaysFrontier, 'domainDelays','domain', delete = True)
    
    
    
def storeDisallowed():
    storeInTable(disallowedURLCache, "disalloweUrls")
    storeInTable(disallowedURLCache, "disalloweUrls")
        
    

    # frontierId = 0
    # for url in frontier:
    #     crawlerDB.execute(
    #         """
    #         INSERT INTO frontier
    #         (id, url, schedule, delay, incomingLinks, domainLinkingDepth,linkingDepth)
    #         VALUES (?, ?, ?, ?, ?, ?, ?)
    #         """,
    #     ( frontierId, url,
    #             frontier[url],
    #             frontierDict[url]["delay"],
    #             json.dumps(frontierDict[url]["incomingLinks"]),
    #             frontierDict[url]["domainLinkingDepth"],
    #             frontierDict[url]["linkingDepth"]))
    #     frontierId +=1

     


# stores the disallowedDomainsCache, and the disallowedURLCache, 
# also makes sure, that no urls form the disallowedURLCache get
# get stored, whose domain is in the disallowedDomainsCache
# def storeDisallowed():
#     id = getLastStoredId("disallowedDomains")
#     for domain in disallowedDomainsCache:
#         crawlerDB.execute(
#             """
#             INSERT INTO disallowedDomains
#             (id, data)
#              VALUES (?, ?)
#                 """,
#         (id, str(disallowedDomainsCache[domain])))
#     id = 0   
#     for url in disallowedURLCache:
#          domain = getDomain(url)
    
#     if not domain:
#         return
#         cursor = crawlerDB.execute(f"SELECT * FROM disallowedDomains WHERE url = ? ",(domain,))
#         items = cursor.fetchone()
        
#         if not items:
#             crawlerDB.execute(
#                 """
#                 INSERT INTO disallowedURL
#                 (id,reason, counters)
#                 VALUES (?, ?)
#                     """,
#             (id, disallowedURLCache[url]["reason"], str(disallowedURLCache[url]["data"])))
            

    
        
        
        
  


    
    

  
  
def storeStrangeUrls():
    id = getLastStoredId("strangeUrls")+1
    for index in range(len(strangeUrls)):
        crawlerDB.execute(
            """
            INSERT INTO strangeUrls
            (id, url, received)
            VALUES (?,?,?)
            """,
        (id,  strangeUrls[index], time.ctime()))
        id = id+1
        
        crawlerDB.commit()
 

def storeCache(forced=False):
    if len(cachedUrls) > 1000 or forced:
        
        # for url in cachedUrls:
        #     cachedUrls[url]["incoming"] = json.dumps(cachedUrls[url]["incoming"])
            
        storeInTable(cachedUrls,"urlsDB", "url", ["incoming"])
        # rows = []                       # collect rows first

        # for url in cachedUrls:
        #     data = cachedUrls[url]
        #     crawlerDB.execute(
        #         """
        #         INSERT INTO urlsDB
        #         (id, url, title, text, lastFetch, outgoing, incoming,
        #         domainLinkingDepth, linkingDepth, tueEngScore)
        #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        #         """,
        #     ( id, url,
        #             data["title"],
        #             data["text"],
        #             data["lastFetch"],
        #             data["outgoing"],
        #             json.dumps(data["incoming"]),
        #             data["domainLinkingDepth"],
        #             data["linkingDepth"],
        #             data["tueEngScore"]))
        #     id = id+1
    if len(cachedUrls) > 1000:
        cachedUrls.clear()
        
def cleanUpDisallowed():
    disalloweURLCache =[url for url in disallowedURLCache if getDomain[url] not in disallowedDomainsCache]
    return disallowedURLCache
    
    
        

# rea
def readAndDel(table, column, identifier, delete=False):
    cursor = crawlerDB.execute(f"SELECT * FROM {table} WHERE {column} = ? ",(identifier,))
    crawlerDB.commit()
    col_names = [desc[0] for desc in cursor.description]
    found = cursor.fetchone()
    
    if delete:
        crawlerDB.execute(f"DELETE FROM {table} WHERE {column} = ?", (identifier,))
        crawlerDB.commit()
    
    if not found:
        return None
    
    foundDict = dict(zip(col_names, found))     
    return foundDict       
    
            
                  
# looks the stored information for the url up, either in cachedUrls, or in urlsDB
# finds the entry and returns it and deletes it
# TODO: IMPLEMENT
def  readAndDelUrlInfo(url, delete=True):
    if url in cachedUrls:
        return cachedUrls[url]
    
    else:
        infoDict = readAndDel("urlsDB", "url", url, delete= delete)
        if infoDict:
            infoDict["incoming"] = json.loads(infoDict["incoming"])
            del infoDict["url"]
            del infoDict["id"]
        return infoDict
        

# loads the stored frontier into the cache- variable frontier
def loadFrontier():
    readTable(frontier, "frontier", "schedule, url", "url",[])
    readTable(frontierDict, "frontier", "url, incomingLinks, linkingDepth, domainLinkingDepth, delay", "url", ["incomingLinks"])
    readTable(domainDelaysFrontier, 'domainDelays', "domain, delay", "domain" )
    # rows = crawlerDB.execute("SELECT * FROM frontier").fetchall()
    # columns = [desc[0] for desc in crawlerDB.description]
    # dictList = [dict(zip(columns, row)) for row in rows]
    # for item in dictList:
    #     frontier[item["url"]]= item["schedule","url"]
    #     frontierDict[item["url"]]= {
    #         "incomingLinks":json.loads(item["incomingLinks"]),
    #         "linkingDepth":item["linkingDepth"],
    #         "domainLinkingDepth":item["domainLinkingDepth"],
    #         "delay":item["delay"]
    #     }
    
    
    # id = getLastStoredId(frontier)
    # while True:
    #     result = readAndDel("frontier", "id", id)
    #     if result:
    #         url = result["url"]    
    #         frontierDict[url]["incomingLinks"] = json.loads(result["incomingLinks"])
    #         frontierDict[url]["delay"] = result["delay"]  
    #         frontierDict[url]["linkingDepth"]
    #         frontierDict[url]["domainLinkingDepth"]
    #         frontier[url]= result["schedule"]
            
    #     else:
    #         break
    #     id = id+1

# returns True, if the url is already in storage, either in cachedUrls or in urlsDB, otherwise returns false
# def isUrlStored(url):
#     stored = False
#     if url in cachedUrls:
#          return True
        
#     stored = crawlerDB.execute(
#         "SELECT EXISTS (FROM urlsDB WHERE id = ?)",
#         [url]
#     ).fetchone()[0] 
#     crawlerDB.commit()
    
     
#     return stored

# checks if there is an entry for the url in the disallowedDomainsCach, in the
# disallowedURLCache, in the disallowedDomainsDB, or in the disallowedURLDB if this
# the case, then it returns True, otherwise it returns False

def findDisallowedUrl(url):
    domain = getDomain(url)
    
    if not domain:
        return False
    disallowed = False

    if domain in disallowedDomainsCache:
        disallowed = True
    elif url in disallowedURLCache:
        disallowed = True
    return disallowed

def findUrl(url):
    if url in cachedUrls:
        return True
    else:
        return  crawlerDB.execute("SELECT EXISTS (FROM urlsDB WHERE id = ?)",
        [url]).fetchone()[0] 
        crawlerDB.commit()

# safes the columns in columns in the specified table as a csv file
# note that columns is a string of form "column1, column2, column3..."
# This function was written by chatGPT
def saveAsCsv(table, columns,limit):
    table_exists = crawlerDB.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{table}'
    """).fetchone()[0]

    if not table_exists:
        print(f"Table '{table}' does not exist. Skipping export.")
        return

    result = crawlerDB.execute(f"SELECT COUNT(*) FROM {table} ").fetchone()[0]
    if result > 0:
        query = f"""
            COPY (
                SELECT {columns} FROM {table} ORDER BY id DESC LIMIT {limit}
            ) TO '{table}.csv' (HEADER, DELIMITER ',')
        """
        crawlerDB.execute(query)
        crawlerDB.commit()

    

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
def extractTheRobotsFile(robotText): 
    
    if not robotText:
        return None
    textList = robotText.splitlines()
    textList = [''.join(a.split()) for a in textList]
    textList = [a for a in textList if not a.startswith('#') and not a=='']
    textList1 = [a.lower() for a in textList]
    rulesStart = False
    agentBoxStart = False
    
    robotsDictionary = {"allowed": [], "forbidden": [], "delay": 1.5}
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
                try:
                    robotsDictionary["delay"] = float (re.searcch(r"([\d.]+)", key).group(1))
                except:
                    pass
            
            #Since we want to crawl structure aware, we decided that sitemaps are not relevant for us
            elif key == "sitemap":
                pass
                #robotsDictionary["sitemap"] = item[indexOfColon+1:]
            elif key == "user-agent":
                agentBocStart = False
                rulesStart = False
            else:
                pass
                #Sometimes there is extra- info in the file since crawlers usually just ignore other
                # then the mentioned fields we don't need this
                # raise ValueError(f"Somehow the implemented rules are not sufficient, there is a word {key} at the beginning of the file")

    return robotsDictionary

def robotsTxtCheck(url, robotText):
    domain = getDomain(url)
    if not domain:
        return (10, False)
    
    roboDict = {}
    value = (10, False)
    allowedMatch, forbiddenMatch = 0,0

    if domain in robotsTxtInfos:
        roboDict = robotsTxtInfos[domain]
        
    else:
        roboDict = extractTheRobotsFile(robotText)
        if not robotText:
            if domain not in domainDelaysFrontier:
                  domainDelaysFrontier[domain] = 1.5   
            return (1.5, True)

        robotsTxtInfos[domain] = roboDict
        
    allowedMatch = longestMatch(roboDict["allowed"], url)
    forbiddenMatch = longestMatch(roboDict["forbidden"], url)
    
    if allowedMatch > forbiddenMatch or allowedMatch == forbiddenMatch:
        if domain in domainDelaysFrontier:
            domainDelaysFrontier[domain] = max(domainDelaysFrontier[domain], roboDict["delay"])
        else:
            domainDelaysFrontier[domain] = roboDict["delay"]
        value = (roboDict["delay"], True)  
    

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
    domain = getDomain(url)
    
    if domain:
        frontierDict[url] = info
        
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
    domain = getDomain(url)
    newUrl = url
    values = [True, url]
    
    if not domain:
        raise Error(f'''T {url}" has no recognizable domain,, but this should have been detected much 
                    earlier in the call hierarchy!''')
    
    if 299< code or code > 400:
        return values

    if location:
        newUrl = location
        newDomain = getDomain(newUrl)
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
    domain = getDomain(url)
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
#%%%
# does search for clickable urls in both html and xml 
# def extractURLs(text,baseUrl):
#      urls = re.findall(r'''href\s*=\s*(".+?"|'.+?')''', text, re.DOTALL)
#      urls = [a[1:-1] for a in urls if a[1:-1].startswith(("/","http"))]
#      full_urls = []
#      for url in urls:
#         try:
#             full_urls.append(urljoin(baseUrl, url) )
#         except ValueError:
#             strangeUrls.append(url)
            
#      full_urls = [html.unescape(a) for a in full_urls]

# chagpt wrote parts of this: Pro: also works with xml, which the former function (commented out) does not
def extractUrls(text, base_url,):
    soup_type = "xml" if "<?xml" in text or "<rss" in text or "<feed" in text else "html.parser"
    try:
        
        soup = BeautifulSoup(text, soup_type)

        urls = set()

        # --- HTML: clickable hrefs ---
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith(("http", "/")):
                urls.add(urljoin(base_url, href))

        # --- XML: link tags and enclosures ---
        for tag in soup.find_all(["link", "enclosure"]):
            # Handle both: <link href="..."/> and <link>https://...</link>
            url = tag.get("href") or tag.get("url") or tag.string
            if url and url.strip().startswith(("http", "/")):
                try:
                    urls.add(urljoin(base_url, url.strip()))

                except ValueError:
                    strangeUrls.append(url.strip())

        # Unescape HTML entities (e.g. &amp;)
        urls = [html.unescape(u) for u in urls]
        # we don't wanit urls linking to sitemaps, because we decided to 
        # crawl site- structure aware (we store the depth of a link inside a site in cachedUrls[url]["linkingDepth"])
        finalUrls = [url for url in urls if not isSitemapUrl(url)]
        return finalUrls
    except:
        return []
        
        
 #%%
 
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
def statusCodesHandler(url, location, code, info):
    # for the question if it makes sense to disallow a whole domain
    # we calculate an UTEMA- weighted average, that is what the sample- value is for
    sample = 0.25
    domain = getDomain(url)

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
    
    return result
    
    
# this function updates the information of urls in the cached urls or in storage
def updateInfo(url, parentUrl, info, score):
    from metric import metric
    # If there was indeed an entry for this url in cache or storage, 
    # this value will be turned to True, this value is the return- value 
    updated = False
    
    if not parentUrl:
        return False
    domainParent = getDomain(parentUrl)
    domainUrl = getDomain(url)
    info_1 = copy.deepcopy(info)
    
    # since we don't want anything to break here, and 
    # nothing happens if this function just does nothing (frontierWrite then just finishes
    # without doing anything as well)
    if not domainParent or not domainUrl:
        return True
    
    if info:
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
    
    
        # Here we maybe want to update the tueEngScore if
        # some of the latter instructins changed the info    
        if info != info_1:
            info["tueEngScore"] = metric(info, url)
        cachedUrls[url] = info
    return updated
        
# this is only called, if the url is already in the frontier
def updateFrontier(url, ancestorUrl, score):
    domain = getDomain(url)
    
    if domain:
        ancestorDomain = getDomain(ancestorUrl)
        if domain == ancestorDomain:
            frontierDict[url]["domainLinkingDepth"] = (min(frontierDict[ancestorUrl]
                                                ["domainLinkingDepth"]+1,frontierDict[url]["domainLinkingDepth"] ))
        else:
            frontierDict[url]["linkingDepth"] = (min(frontierDict[ancestorUrl]
                                                ["linkingDepth"]+1,frontierDict[url]
                                                ["linkingDepth"] ))
        frontierDict[url]["incomingLinks"].append([ancestorUrl,score])

    
    
    
    
    
    
    
# this function gets an url, reads all urls that are of interest to us and then checks for each of them if they
# are still admissible, i.e, if they have been disallowed or if they are already stored, in this case some of their
# information needs to be updated (happens via updateInfo). If this is not the case, it throws a list with entries of the form [<Unix time starting at which access to the url is allowed>, url, {"delay": <delay>, "linkingDepth": "domainLinkingDepth": <integer>, "incomingLinks": < list of parent- urls with tueEngScores>}] into the frontier
def frontierWrite(url, robotText, predURL, score):
    domain = getDomain(url)
    if not domain:
        pass
    elif url in frontier and predURL:
        updateFrontier(url, predURL, score) 
    elif findDisallowedUrl(url):
        pass
    elif updateInfo(url, predURL,readAndDelUrlInfo(url),score):
        pass
    else:
        robotsCheck = robotsTxtCheck(url,robotText)
    
        if robotsCheck [1]:
            if url not in frontierDict:
                frontierDict[url] = {}
            # This is only the case, if the url was part of the seed list
            if not predURL:
                frontier[url] = time.time()
                frontierDict[url] ["domainLinkingDepth"] = 0
                frontierDict[url]["linkingDepth"] = 0
                frontierDict[url]["delay"] = domainDelaysFrontier[domain]
            
            else:
                frontier[url] = time.time() + domainDelaysFrontier[domain]
                
                predDomain = getDomain(predURL)
                

                if domain == predDomain:
                    frontierDict[url] ["domainLinkingDepth"] = frontierDict[predURL]["domainLinkingDepth"]+1
                    frontierDict[url]["linkingDepth"] = frontierDict[predURL]["linkingDepth"]
                elif not predDomain:
                    raise Error(f" The url {predURL} has no predDomain")
                    pass     
                else:
                    frontierDict[url]["domainLinkingDepth"] = 0
                    frontierDict[url]["linkingDepth"] = frontierDict[predURL]["linkingDepth"]+1
                
                    
                frontierDict[url]["delay"] = domainDelaysFrontier[domain]
            if "incomingLinks" not in frontierDict[url]:
                frontierDict[url]["incomingLinks"] = []
                    
            else: 
                frontierDict[url]["incomingLinks"].append([predURL, score])

    
        if ["domainLinkingDepth", "linkingDepth", "delay", "incomingLinks"] != list(frontierDict[url].keys()):
            raise Error("Some key is missing here!")
                        

    
async def fetchSingleResponse(client,url):
    urlDict = {
            "url": url,
            "responded": False
        }
    robot = ""
    try:
        response = await client.get(url)
    
        try:
            robotResponse = await client.get(urljoin(url, "/robots.txt"))
            
            robot = robotResponse.text
        except:
            pass
    
            

        return {
            "url": url,
            "text": response.text,
            "robot": robot,
            "code": response.status_code,
            "contentType": response.headers.get("Content-Type"),
            "location": response.headers.get("Location"),
            "retry" : response.headers.get("Retry-Value"),
            "responded": True
        }
    except:
         return urlDict
         
         
async def fetchResponses(lstOfUrls):
    timeout = httpx.Timeout(1.5) 
    async with httpx.AsyncClient(timeout=timeout, headers= headers, follow_redirects= False ) as client:
        tasks = [fetchSingleResponse(client, url) for url in lstOfUrls]
        responses = await asyncio.gather(*tasks)
        return responses

def lstAllDifferentDomains(maxLength):
    resultList = []
    domainList = []
    l = 1
    listOfPoppedItems = []
    lHeap = len(frontier)
    counter = 0
    while l<maxLength and counter < lHeap :
        url, scheduled = frontier.popitem()
        domain = getDomain(url)
        t = time.time()
        if scheduled <= t and domain:
                if domain not in domainList:
                    resultList.append(url)
                    domainList.append(domain)
                    l += 1
                    
                else:
                    listOfPoppedItems.append((url, scheduled))
        else:
            listOfPoppedItems.append((url,scheduled))
        
        counter += 1
            
    for url, scheduled in listOfPoppedItems:
        frontier[url] = scheduled
        
    return resultList 
        
def frontierRead(urlDict, info):
    from metric import metric
    url = urlDict["url"]
    response = urlDict["responded"]
    
    if response:
        code = urlDict["code"]
        contentType = urlDict["contentType"]
        location = urlDict["location"] 
        rawText = urlDict["text"]
        robot = urlDict["robot"]
        robotsTxtCheck(url, robot)
        if urlDict["retry"]:
            retry(urlDict["retry"])
             
        valid, newUrl = statusCodesHandler(url,location, code,info)
    else :
        statusCodesHandler(url,None,None,info)
        return (False, url)

    if not valid:
        return (False, url)
    
    if newUrl != url:
        if newUrl:
            if frontierDict[url]["incomingLinks"]:
                parentUrl = frontierDict[url]["incomingLinks"][:-1]
                frontierWrite(newUrl,robot,  parentUrl, readAndDelUrlInfo(parentUrl)["tueEngScore"])
                
            # this can only be the case, if the url was a seed url
            else:
                frontierWrite(newUrl, None, 1)
        else:
            pass
        
        return (False, newUrl )    
    else:
                
        cachedUrls[url] =  {"title": "", "text": "","lastFetch": time.time(), "outgoing": [], "incoming": [],
                                        "domainLinkingDepth":5, "linkingDepth": 50, "tueEngScore": 0.0}
            
        info = cachedUrls[url]
        textAndTitle = getText(rawText, contentType)
        info["title"] =textAndTitle[1]
        text = textAndTitle[0]
        info["text"] = text
        info["lastFetch"] = time.time()
        # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
        #     print("2dfsfsfsf-------not in frontier------")
        try:
            info["incoming"]= frontierDict[url]["incomingLinks"]
        except:
            raise Error(f"fails with url {url}")
        info["outgoing"] = extractUrls(rawText, url)
        info["linkingDepth"] = frontierDict[url]["linkingDepth"]
        info["domainLinkingDepth"] = frontierDict[url]["domainLinkingDepth"]
        
        info["tueEngScore"] = metric(info, url)
        if info["tueEngScore"] >-1:
            # why  info["domainLinkingDepth"]<5 ? Well the the amount of links
            # to get from the main page of uni tübingen to the webpage of an computer 
            # science professor is roughly 5
            if info["domainLinkingDepth"]<5 and info["linkingDepth"]<5:
                #if len(info["outgoing"]) == 0:
                #       raise Error(f"sucessorUrl in None, the outgoing list is {url}")
                for successorUrl in info["outgoing"]:
                    frontierWrite(successorUrl,robot, url, info["tueEngScore"])
        moveAndDel(url, "success")
    return (True, url)
        
# maxNumberOfUrls is very important, since it controls the maximal number of parallel 
# http requests       
def manageFrontierRead():
    lastStoredUrl = ""
    maxNumberOfUrls = 20
    urlsList = lstAllDifferentDomains(maxNumberOfUrls) 
    responses = asyncio.run(fetchResponses(urlsList))
    for urlDict in responses:
        url = urlDict["url"]
        success,_ = frontierRead(urlDict, frontierDict[url])
        if success:
            lastStoredUrl = url
        
    return lastStoredUrl
        
    
    
    
# this is only called for urls which are neither in the caches nor in the
# databases, it reads the entry of the frontier with the smallest time to wait
# and creates the information for the storage for it, if the http- request #works out (if not the url is rescheduled via the handleCodes in 
# statusCodeHandler), or after too many rescheduling, just deleted, and 
# in some cases it even goes into the disalloweURLCache, or the domain 
# goes into the disallowedDomainsCache, for mor information see handleCodes). Further if the request works out, generated information is stored in cachedURLs
# def frontierRead(info, url, schedule):
#     wait = schedule -time.time()
#     if wait > 0:
#         # make the program stoppable, even if the wait for the first element in the frontier is hudge
#         for i in range(10* math.ceil(wait)):
#             time.sleep(1/10)
#             if not inputDict["crawlingAllowed"]:
#                 return
        
    
#     response = getHttp(url)
    
#     if response:
#         code = response.status_code
#         if response.headers.get("Retry-value"):
#             retry(response.headers.get("Retry-value"))
#         location = response.headers.get("Location")  
#         valid, newUrl = statusCodesHandler(url,location, code,info)
#         contentType = response.headers.get("Content-Type", "")
#     else :
#         statusCodesHandler(url,None,None,info)
#         return

#     if not valid:
#         return
    
#     if newUrl != url:
#         if newUrl:
#             if frontierDict[url]["incomingLinks"]:
#                 parentUrl = frontierDict[url]["incomingLinks"][:-1]
#                 frontierWrite(newUrl, parentUrl, readAndDelUrlInfo(parentUrl)["tueEngScore"])
                
#             # this can only be the case, if the url was a seed url
#             else:
#                 frontierWrite(newUrl, None, 1)
#         else:
#             pass
#     else:
                
#         cachedUrls[url] =  {"title": "", "text": "","lastFetch": time.time(), "outgoing": [], "incoming": [],
#                                         "domainLinkingDepth":5, "linkingDepth": 50, "tueEngScore": 0.0}
            
#         info = cachedUrls[url]
#         rawText = response.text
#         textAndTitle = getText(rawText, contentType)
#         info["title"] =textAndTitle[1]
#         text = textAndTitle[0]
#         info["text"] = text
#         info["lastFetch"] = time.time()
#         # if f"https://www.medizin.uni-tuebingen.de/en-de/startseite" in frontierDict:
#         #     print("2dfsfsfsf-------not in frontier------")
#         try:
#             info["incoming"]= frontierDict[url]["incomingLinks"]
#         except:
#             raise Error(f"fails with url {url}")
#         info["outgoing"] = extractUrls(rawText, url)
#         info["linkingDepth"] = frontierDict[url]["linkingDepth"]
#         info["domainLinkingDepth"] = frontierDict[url]["domainLinkingDepth"]
        
#         info["tueEngScore"] = metr.metric(info, url)
#         if info["tueEngScore"] >-1:
#             # why  info["domainLinkingDepth"]<5 ? Well the the amount of links
#             # to get from the main page of uni tübingen to the webpage of an computer 
#             # science professor is roughly 5
#             if info["domainLinkingDepth"]<5 and info["linkingDepth"]<5:
#                 #if len(info["outgoing"]) == 0:
#                 #       raise Error(f"sucessorUrl in None, the outgoing list is {url}")
#                 for successorUrl in info["outgoing"]:
#                     frontierWrite(successorUrl,url, info["tueEngScore"])
#         moveAndDel(url, "success")
        
    
    
        
        
    
        
        
        
         

    

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

    
 
# def isUrlAllowed(url):
#     domain = getDomain(url)
    
#     if domain in disallowedDomainsCache:
#         pass
        

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
    
            

            
    #         # if cmd == "newSeed":
    #         #     print('''The program waits for the path to the seed. It has to be of the a correct path, starting from the folder crawler ''')
    #         #     cmd = input():
    #         #     if
                
    #         if cmd == "frontier":
    #             print(f"the frontier has currently {len(frontier)} entries")
    #             # print("these are the entries with the longest waiting time currently:")
    #             # frontier_ = copy.deepcopy(frontier)
    #             # frontierDict_ = copy.deepcopy(frontierDict)
    #             # for index in range(min(10, len(frontier_)-1)):
    #             #     url = list(frontier_)[-(index-1)]
    #             #     print(f'''url : {url}, time(human readble): {datetime.fromtimestamp(frontier_[url])}, delay: {frontierDict_[url]["delay"]}''')
                        
    #         if cmd == "errors":
    #             print(f"the responseHttpsErrorTracker has {len(responseHttpErrorTracker)} entries")
    #             respoCopy = copy.deepcopy(responseHttpErrorTracker)
    #             for index in range(min(10, len(frontier)-1)):
    #                 if frontier != []:
    #                     url = list(frontier)[-(index-1)]
    #                     if getDomain(url) in respoCopy:
    #                         print(f'''In the domain {getDomain(url)} these were the last status_codes at the times: {[a[1] for a in respoCopy[getDomain(url)]["data"]]}''')
    #                         print("--------------------------")
    #                 else:
    #                     print("The frontier is empty")
                
    #         if cmd == "cachedUrls":
    #             print(f"the there are {len(cachedUrls)} urls in cachedUrls")
    #             # cachedUrls_ = copy.deepcopy(cachedUrls)
    #             # for index in range(min(10, len(frontier)-1)):
    #             #     if frontier != []:
    #             #         url = list(cachedUrls_)[-index-1]
    #             #         print(f'''url : {url}, time last fetched: {datetime.fromtimestamp(cachedUrls_[url]["lastFetch"])}, title : {cachedUrls_[url]["title"]}, tueEngScore: {cachedUrls_[url]["tueEngScore"]}
    #             #         ''')
    #             #     else:
    #             #         print("The frontier is empty")

                
    #         if cmd == "disabledUrls":
    #             print(f"there are  {len(disallowedURLCache)} blocked Urls so far")
                
    #         if cmd == "disabledDomains":
    #             print(f"there are  {len(disallowedDomainsCache)} blocked domains so far")
                
                
    #         # shows the size of urlsDB, aka the number of urls already in storage
    #         if cmd == "storedUrls":
    #             print(f'There are  {crawlerDB1.execute("SELECT COUNT(*) FROM urlsDB").fetchone()} stored urls so far')
                
    # crawlerDB1.close()     
            


# initialises the frontier
# gets a list of urls, creates frontier- items from that with initial values 
def frontierInit(lst):
    for url in lst:
        frontierWrite(url,None,None,1)
        
    


# this is the crawler function, it maintains the caches (puts them into storage)
# if necessary, and opens
# gets the initial seed list as input
def crawler(lst):#inputThread):
    # IMPORTANT: Activate this in order to load the earlier frontier from the database
    print("Input not yet available, please wait!")
    global inputDict
    frontierInit(lst)
    loadFrontier()
    readTable(disallowedDomainsCache, 'disallowedDomains','domain, received, data', "domain", unpacks = ["received"])
    readTable(disallowedURLCache, 'disallowedUrls','url, received, reason', "url", unpacks = ["received"])
    readTable(responseHttpErrorTracker, 'errorStorage','domain, data, urlData', "domain",["data", "urlData"])
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
            storeCache()
            lastCachedUrl = manageFrontierRead()
            counter +=1
            l = len(frontier) 
                
        if l == 0 or stopEvent.is_set():
            print(f"last storedUrl: {lastCachedUrl}")
            break
        
    
        if counter % 10 == 0:
            counter = 0
            print("---------------------------------------------------")
            print(f"the actual number of cachedUrls: {len(cachedUrls)}")
            print(f"the actual number of errors: {len(responseHttpErrorTracker)}")
            print(f"the size of the frontier: {l}")
            print(f"the actual number disallowedUrls: {len(disallowedURLCache)}")
            print(f"the actual number disallowedDomains: {len(disallowedDomainsCache)}")
            print(f'There are  {crawlerDB.execute("SELECT COUNT(*) FROM urlsDB").fetchone()} stored urls so far')
            for index in range(min(10, len(frontier)-1)):
                if frontier != []:
                    url = list(frontier)[-(index-1)]
                    if getDomain(url) in responseHttpErrorTracker:
                        print(f'''In the domain {getDomain(url)} these were the last status_codes at the times: {[a[1] for a in responseHttpErrorTracker[getDomain(url)]["data"]]}''')
                        print("--------------------------")
            print("---------------------------------------------------")
            
        
    stopEvent.set()      
     # IMPORTANT: Activate this in order to store cachedUrls into the database, when the program stops
    storeCache(True)
    
    # deletes the urls for which the domains are in 
    # disallowedDomainsCache
    cleanUpDisallowed()  
    storeInTable(disallowedURLCache, 'disallowedUrls', "url", delete= True, pack = ["received"])
    storeInTable(disallowedDomainsCache, 'disallowedDomains', "domain",delete= True, pack = ["received"])
    storeInTable(responseHttpErrorTracker, 'errorStorage', "domain", ["data", "urlData"], delete= True)
    # IMPORTANT: Activate this, in order to store the frontier into the database, when the program stops
    storeFrontier()
    #IMPORTANT: Activate this, in order to store a list of strings that could not have been detected as urls
    # but still where in href="..."
    storeStrangeUrls()
    
    print(f"the actual number of cachedUrls: {len(cachedUrls)}")
    print(f"the actual number of tracked websites (because of http- statuscode): {len(responseHttpErrorTracker)}")
    print(f"the size of the frontier: {len(frontier)}")
    print(f"the actual number disallowedUrls: {len(disallowedURLCache)}")
    print(f"the actual number disallowedDomains: {len(disallowedDomainsCache)}")


def runCrawler(lst):
    if __name__ == "__main__":
        try:    
            os.remove("crawlerDB.duckdb.wal")
        except:
            pass
        try:
            os.remove("crawlerDB.duckdb")
        except:
            pass
        crawler(lst) #)
        # If you want to save the frontier or the urlsDB as csv, activate either
        saveAsCsv("frontier", "id, schedule, delay, url",10)
        saveAsCsv("urlsDB", "url, lastFetch, tueEngScore",100)
        print("[MAIN] crawler finished")
        crawlerDB.commit()
        crawlerDB.close()
        
        #crawlerDB.close()

            
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