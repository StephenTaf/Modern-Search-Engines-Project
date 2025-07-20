
from requests.adapters import HTTPAdapter
import heapdict
import time
import matplotlib.pyplot as plt
import copy
import asyncio
from databaseManagement import (store, load, storeCache, findDisallowedUrl, readUrlInfo, printNumberOfUrlsStored 
     ,updateTableEntry, closeCrawlerDB)
import helpers
import statusCodeManagement
from robotsTxtManagement import robotsTxtCheck
import robotsTxtManagement
from statusCodeManagement import statusCodesHandler
from urlRequestManagement import fetchResponses
import statusCodeManagement
import helpers

##############################################
# This file is about dealing with the frontier (filling it, reading it out, extracting new urls, updating the caches if necessary)
##############################################
  
  ###### some global variables ########
# in order to be able to raise customed- errors
class Error(Exception):
    pass



# frontier is of the form {url: schedule}
#, where url is just an url and schedule is the unix- time from which on craling will be allowed for this url,
# i.e. frontierManagement.manageFrontierRead processes this url only when reality has reached at least that unix-time
frontier = heapdict.heapdict()

# this dictionary is of the form {url: {"delay": delay:, "incomingLinks": incomingLinks, "linkigDepth": linkingDepth, "domainLinkingDepth" :
# domainLinkingDepth}}, the fields meanings can be just taken from the comment in databaseManagement.py regarding the table frontier
frontierDict = {}

# contains entries of form <domain-name>: delay
# delay is the minimal crawl- delay for every url on that domain 
domainDelaysFrontier = {}



# this is the cache for the already stored urls
# its entries have the form url: {"text":text, "title": title, "incoming": incoming, "domainLinkingDepth": domainLinkingDepth, 
# "linkingDepth": linkingDepth, "tueEngScore": tueEngScore}, more information about the entries
# can be found in the table urlsDB in databaseManagement
cachedUrls = {}



# this cache stores the URLs for which we suspect (temporal) blocking
# the entries have the form url:{"reason": reason, "data": code, "received": time}
# the palceholders have the following meaning:
#
#   - url: the url that this entry disallows
#   - reason: "counter" or "loop", for more information see the comments in the body of frontierManagement.moveAndDel
#   - code: the http- status-code which lead statusCodeManagement.handleCodes or statusCodeManagement.handle3xxLoop
#           to call frontierManagement.moveAndDel creating this entry
#   - receive: Just the human- readible time at which the last code of the kind that lead to us considering this url as
#              disallowed (i.e. creating an entry in this dictionary) was received
disallowedURLCache = {}
# this cache stores the domains for which we suspect (temporal) blocking
# the entries have the form domain:{"data": [(time,code),...], "received": received}
# the palceholders have the following meaning:
#
#   - domain: the domain that this entry disallows
#   - (time,code) each of these tuples is representing one http- response status- code, code received at human- readible time time
#   - received: Just the human- readible time at which this entry was written
disallowedDomainsCache = {}

  

              
# input:
#       - url: the current url for which we want to update the information stored in frontierDict 
#       - ancestorUrl: The name of the url which either redirected (over a path of length < 5) to this url,
#        or linked to the url on which we fetched this url and stored it in the frontier
#       - score: The tueEngScore of the ancestorUrl
#
# what this function does: 
# It updates the list of incoming links, the domainLinkingDepth and the linkingDepth of the given url, all of
# those are used in the metric fucntion of metric.py, which is called in frontierRead belowe this function here. 
# For further information about these measurements, see the comments about
# the table urlsDB in the CrawlerDB database in the file databaseManagement.py 
def updateFrontier(url, ancestorUrl, score):
    '''updates urls domainLinkinDepth, and linkingDepth metrics, as well as the incomingLinks in frontierDict'''
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

    
    
    
    
# input:
#       url: this is just the url for which we want to write or update a frontier entry if we are allowed according to the robotsfile
#       robotText: This is either None (if fetchSingleResponse in urlRequestManagement.py did not find a robots.txt- file, or the 
#       trying to find one failed for some reason)
#       predUrl: The url of the website on which we last found a link to this url
#       score: The tueEng score of the predUrl website
#
# What this function does:
# It checks if the url is in the frontier, if so it updates the url by calling updateFrontier, further it checks if this url
# was for some reason disallowed earlier on (if we suspected (short- time) blocking of our crawler) via calling findDisallowedUrl
# if this was the case this function does nothing. If all of this is not the case it checks if our crawler is allowed to access the
# wepsite the url belongs to ny running a robotsTxtCheck. If this is successful it proceeds to write the entries for the given url
# into the frontier and the frontierDict 
def frontierWrite(url, robotText, predURL, score):
    '''if not already visited, scheduled to visit, or forbidden, creates a frontier and frontierDict entry for the given url'''
    domain = helpers.getDomain(url,strangeUrls=helpers.strangeUrls)
    if not domain:
        pass
    elif url in frontier and predURL:
        updateFrontier(url, predURL, score) 
    elif findDisallowedUrl(url, disallowedDomainsCache, disallowedURLCache):
        pass
    elif updateInfo(url, predURL,readUrlInfo(cachedUrls, url),score):
        pass
    else:
        robotsCheck = robotsTxtManagement.robotsTxtCheck(url,robotText, domainDelaysFrontier=domainDelaysFrontier)
    
        if robotsCheck [1]:
            if url not in frontierDict:
                 frontierDict[url] = {"domainLinkingDepth":0, "linkingDepth":0, "delay": 1.5, "incomingLinks": []}
            
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
            # if "incomingLinks" not in frontierDict[url]:
            #     frontierDict[url]["incomingLinks"] = []
                    
            # else: 
            frontierDict[url]["incomingLinks"].append([predURL, score])

            test = list(frontierDict[url].keys())
            if ["domainLinkingDepth", "linkingDepth", "delay", "incomingLinks"] != test:
                raise Error("Some key is missing here!")
                        

    
# input:   
#       - urlDict: This contains information fetched by fetchSingleResponse in urlRequestManagement.py for a single url
#       - info: this is just frontierDict[url] for that url
# 
# what this function does: 
# checks if the url stored in urlDict came from a valid http- resoponse (status- code of form 2.xx or sometimes 3.xx (see handleCodes
# and handle 3xxLoop in statusCodeManagement.py for more information on that)), if it did but it relocated to a new url, the new url is
# written into frontierDict and frontier by usage of frontierWrite, and nothing else happens. If it is valid and no relocation happened,
# then the url is processed, meaning an entry is created in cachedUrls and afterwards it is deleted from all the caches by using moveAndDel.
# Furthermore it writes all the found urls in the content of the site belonging to the url into the frontier and frontierDict by
# usingfrontierWrite.
# For more information on that see moveAndDel.
# if it did 
def frontierRead(urlDict, info):
    ''' processes the url for which it is given information about, and then, if everything runs through makes an entry for '''
    from metric import metric
    url = urlDict["url"]
    response = urlDict["responded"]
    
    if response:
        code = urlDict["code"]
        contentType = urlDict["contentType"]
        location = urlDict["location"] 
        rawText = urlDict["text"]
        robot = urlDict["robot"]
        robotsTxtCheck(url, robot, domainDelaysFrontier)
        retry = helpers.retry(urlDict["retry"])
             
        valid, newUrl = statusCodesHandler(url,location, code,info, retry = retry)
    else :
        statusCodesHandler(url,None,None,info, retry=None)
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
        textTitleAndUrls = helpers.parseTextAndFetchUrls(rawText, contentType, url)
        info["title"] =textTitleAndUrls[1]
        text = textTitleAndUrls[0]
        info["text"] = text
        info["lastFetch"] = time.time()
        info["incoming"]= frontierDict[url]["incomingLinks"]
        info["linkingDepth"] = frontierDict[url]["linkingDepth"]
        info["domainLinkingDepth"] = frontierDict[url]["domainLinkingDepth"]
        
        info["tueEngScore"] = metric(info, url)
        if info["tueEngScore"] >-0.1:
            # Seemed like a good crawling- depth, but in gaining our url- Database we played 
            # around with this value, but this can be used as a good initial value, we think
            # since relevance to Tübingen and English seems to drop when moving further out either
            # domain- wise (linkingDepth) or with regard to the minimum path of connectiing links on a domain itself (domainLinkingDepth)
            if info["domainLinkingDepth"]<5 and info["linkingDepth"]<5:
                #if len(info["outgoing"]) == 0:
                #       raise Error(f"sucessorUrl in None, the outgoing list is {url}")
                for successorUrl in textTitleAndUrls[2]:
                    frontierWrite(successorUrl,robot, url, info["tueEngScore"])
        moveAndDel(url, "success")
    return (True, url)

# what this function does:        
# this function basically collects a list of the first 100 urls, which appear in sequential order in
# the frontier at time of fetching, and satisfy the constraints, that none of the urls can be of the
# same domain (call to lstAllDifferntDomains). It then fetches all these urls asynchronically (using urlRequestManagement.fetchResponses)
# and then gives the fetched information one by one to frontierRead in order to process it.
#
# output: The last stored url, i.e. the last url for which currently was created an entry in cachedUrls
   
def manageFrontierRead():
    '''reads multiple urls of different domains stored in the frontier and processes them'''
    lastStoredUrl = ""
    
    # can be played around with, essentially it limits size of the url - list 
    # which fetchResponses in urlRequestManagement.py gets per call (i.e., the maximal
    # number of possible parallel http- calls)
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
        
        
        
        
        
                   
# usage:        used in handleCodes, handle3xx.Loop
# arguments:    
#               url: the url for which wee want the informations stored/ deleted
#               reason: is one of "success", "average", "counter", "loop"
# return value: 
#               -
# REQURIEMENT: url must be in url- frontier
def moveAndDel(url, reason):
    '''Deletes the url from the caches, an in case of any reason other than "success" creates a disalloweURLCache or disallowedDomainCache entry, dependeing on the reason'''
    domain = helpers.getDomain(url)
    
    if not domain:
        return
    # If there are no errors in the code, this case should never be activated
    if url in frontier:
        urlInFrontier = True
          
        try:
            data =  statusCodeManagement.responseHttpErrorTracker[domain]["data"] 
        except KeyError as e:
            # This should most definitely not happen!
            print("Somehow moveAndDel gets a url for which responseHttpErrorTracker[domain]['data']  does not exist")            
        
    # in this case we check if at some point there 
    # was a failed http- request regarding this message
    # if there was, we delete the associated field, since we now successfull fetched all information we want associated with the url
    # and therefore need no further tracking of http- status- codes from responses with regard to this url
    if reason == "success":
        if domain in statusCodeManagement.responseHttpErrorTracker:
            if url in domain:
                del statusCodeManagement.responseHttpErrorTracker[url]
        if url in frontierDict:
            del frontierDict[url]
            del frontier[url]
        
    # this means that in statusCodeManagement.handleCodes the UTEMA- threshold in the last if- clause in the funciton body was
    # reached, which means we get too many too costly errors from the domain of the url overall, so we don't want to continue to 
    # crawl it, and suspect we might have been blocked at least for now
    elif reason == "average":
        disallowedDomainsCache[domain] = {"data": copy.deepcopy(data), "received": str(time.ctime())}
        del statusCodeManagement.responseHttpErrorTracker[domain]
        for a in frontierDict:
            if domain in a:
                del frontier[a]
                del frontierDict[a]
        
    # this is the case, when there have been too many
    # failed http- requests, with a certain status_code
    # , see handleCodes in statusCodeManagement.py for more details  
    elif reason == "counter":
        disallowedURLCache[url]  = {"reason": "counter", 
            "data": copy.deepcopy(statusCodeManagement.responseHttpErrorTracker[domain]["data"] [-1][1]), "received": statusCodeManagement.responseHttpErrorTracker[domain]["data"] [-1][0]}
        del statusCodeManagement.responseHttpErrorTracker[domain]["urlData"][url]
        if url in frontierDict:
            del frontier[url]
            del frontierDict[url]
        
    
    # this is the case, if there was a redirect- loop
    # detected, see handleCodes and handle3xxLoop in  statusCodeManagement.py for more details  
    elif reason == "loop":
        loopList = statusCodeManagement.responseHttpErrorTracker[domain]["urlData"][url]["loopList"]
        disallowedURLCache[url]  = ({"reason": "loop", 
            "data":  [loopList[0]], "received": time.ctime()})
        for a in loopList:
            if a[0] in frontierDict:
                del frontier[a]
                del frontierDict[a]
        del statusCodeManagement.responseHttpErrorTracker[domain]["urlData"][url]
    
    else:
        raise Exception(f''' the reason '{reason}' that was given to moveAndDel does not
                        exist''')
    
    
    
    
# input:
#       - url: The url for which we want to update its entry in cachedUrls
#       - parentUrl: The url from which we last fetched the current url (read it out of the content), or in case of (multiple)
#       - info: the frontierDict[ur]- entry
#       - score: The tueEngScore of the parentUrl
# output:
#       - returns True, if the cachedUrls- entry was changed and false, if it wasn't
#
#what this function does:
# if updates the linkingDepth and the domainLinkingDepth, as well as the list of incoming urls
# (urls which link to the current one), for more information see comments about the entries of the table urlsDB
# in databaseManagement.py
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


# this function gets a maximal length and lists the first maxLengt number of urls 
# , where each of those url must not be of the same domain, of the urls stored in the frontier and returns them as a list
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
        
                    resultList.append(url)
                    domainList.append(domain)
                    l += 1
                    
        # we add all items back to the frontier, even those we are now about to crawl (those in resultLst) 
        # since otherwise it would break with our goal to delete entries from caches by deletion via
        # moveAndDel only
        listOfPoppedItems.append((url, scheduled))
        
        
        counter += 1
            
    for url, scheduled in listOfPoppedItems:
        frontier[url] = scheduled
        
    return resultList 