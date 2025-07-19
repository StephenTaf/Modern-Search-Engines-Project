  


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
        finalUrls = [url for url in urls if not helpers.isSitemapUrl(url)]
        return finalUrls
    except:
        return []
        
              
# this is only called, if the url is already in the frontier
def updateFrontier(url, ancestorUrl, score):
    domain = helpers.getDomain(url)
    
    if domain:
        ancestorDomain = helpers.getDomain(ancestorUrl)
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
    domain = helpers.getDomain(url,strangeUrls=strangeUrls, useStrangeUrls = True )
    if not domain:
        pass
    elif url in frontier and predURL:
        updateFrontier(url, predURL, score) 
    elif findDisallowedUrl(url, disallowedDomainsCache, disallowedURLCache):
        pass
    elif updateInfo(url, predURL,readUrlInfo(cachedUrls, url),score):
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
                
                predDomain = helpers.getDomain(predURL)
                

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

            test = list(frontierDict[url].keys())
            if ["domainLinkingDepth", "linkingDepth", "delay", "incomingLinks"] != test:
                raise Error("Some key is missing here!")
                        

    
    
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
            retry = retry(urlDict["retry"])
             
        valid, newUrl = statusCodesHandler(url,location, code,info, retry)
    else :
        statusCodesHandler(url,None,None,info)
        return (False, url)

    if not valid:
        return (False, url)
    
    if newUrl != url:
        if newUrl:
            if frontierDict[url]["incomingLinks"]:
                parentUrl = frontierDict[url]["incomingLinks"][:-1]
                frontierWrite(newUrl,robot,  parentUrl, readUrlInfo(cachedUrls, parentUrl)["tueEngScore"])
                
            # this can only be the case, if the url was a seed url
            else:
                frontierWrite(newUrl, None, 1)
        else:
            pass
        
        return (False, newUrl )    
    else:
                
        cachedUrls[url] =  {"title": "", "text": "","lastFetch": time.time(), # "outgoing": [],
                            "incoming": [], "domainLinkingDepth":5, "linkingDepth": 50, "tueEngScore": 0.0}
            
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
        # We decided not to use this in the final version of our crawler: too much storage space
        # info["outgoing"] = extractUrls(rawText, url)
        
        info["linkingDepth"] = frontierDict[url]["linkingDepth"]
        info["domainLinkingDepth"] = frontierDict[url]["domainLinkingDepth"]
        
        info["tueEngScore"] = metric(info, url)
        if info["tueEngScore"] >-0.1:
            # why  info["domainLinkingDepth"]<5 ? Well the the amount of links
            # to get from the main page of uni tübingen to the webpage of an computer 
            # science professor is roughly 5
            if info["domainLinkingDepth"]<5 and info["linkingDepth"]<5:
                #if len(info["outgoing"]) == 0:
                #       raise Error(f"sucessorUrl in None, the outgoing list is {url}")
                for successorUrl in extractUrls(rawText, url):
                    frontierWrite(successorUrl,robot, url, info["tueEngScore"])
        moveAndDel(url, "success")
    return (True, url)
        
# maxNumberOfUrls is very important, since it controls the maximal number of parallel 
# http requests       
def manageFrontierRead():
    lastStoredUrl = ""
    maxNumberOfUrls = 100
    urlsList = lstAllDifferentDomains(maxNumberOfUrls) 
    responses = asyncio.run(fetchResponses(urlsList))
    for urlDict in responses:
        url = urlDict["url"]
        
        success,_ = frontierRead(urlDict, frontierDict[url])
        if success:
            lastStoredUrl = url
        
    return lastStoredUrl



# initialises the frontier
# gets a list of urls, creates frontier- items from that with initial values 
def frontierInit(lst):
    for url in lst:
        frontierWrite(url,None,None,1)
        
        
        
        
        
        
        
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
    domain = helpers.getDomain(url)
    
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
        if url in frontierDict:
            del frontierDict[url]
            del frontier[url]
        
    # this is the case, when there have been "too many"
    # (according to the weighted average, see handleCodes and UTEMA)failed http- requests in a certain domain
    elif reason == "average":
        disallowedDomainsCache[domain] = {"data": copy.deepcopy(data), "received": str(time.ctime())}
        del responseHttpErrorTracker[domain]
        for a in frontierDict:
            if domain in a:
                del frontier[a]
                del frontierDict[a]
        
    # this is the case, when there have been too many
    # failed http- requests, with a certain status_code
    # , see handleCodes   
    elif reason == "counter":
        disallowedURLCache[url]  = {"reason": "counter", 
            "data": copy.deepcopy(responseHttpErrorTracker[domain]["data"] [-1]), "received": time.ctime()}
        del responseHttpErrorTracker[domain]["urlData"][url]
        if url in frontierDict:
            del frontier[url]
            del frontierDict[url]
        
    
    # this is the case, if there was a redirect- loop
    # detected, see handleCodes and handle3xxLoop
    elif reason == "loop":
        loopList = responseHttpErrorTracker[domain]["urlData"][url]["loopList"]
        disallowedURLCache[url]  = ({"reason": "loop", 
            "data":  [loopList[0]], "received": time.ctime()})
        for a in loopList:
            if a[0] in frontierDict:
                del frontier[a]
                del frontierDict[a]
        del responseHttpErrorTracker[domain]["urlData"][url]
    
    else:
        raise Exception(f''' the reason '{reason}' that was given to moveAndDel does not
                        exist''')
    
    
    
    
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

        
        
def lstAllDifferentDomains(maxLength):
    resultList = []
    domainList = []
    l = 1
    listOfPoppedItems = []
    lHeap = len(frontier)
    counter = 0
    while l<maxLength and counter < lHeap :
        url, scheduled = frontier.popitem()
        domain = helpers.getDomain(url)
        t = time.time()
        if scheduled <= t and domain:
                if domain not in domainList:
                # not deleting the frontierDict[url] entry here , even though the frontier[url] entry does 
                # not exist anymore in the frontier (because if was deleted by the pop-
                # operation in the lstAllDifferentDomains ) means we have to be very careful to not forget
                # to delete all entries of frontiderDict as well as soon as we son't need them anymore (see moveAndDel)
                    resultList.append(url)
                    domainList.append(domain)
                    l += 1
                    
                
        listOfPoppedItems.append((url, scheduled))
        
        
        counter += 1
            
    for url, scheduled in listOfPoppedItems:
        frontier[url] = scheduled
        
    return resultList 