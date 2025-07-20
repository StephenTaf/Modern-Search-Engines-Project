import random
import time
from datetime import datetime
from dateutil.parser import parse
from urllib.parse import urljoin, urlparse
from UTEMA import UTEMA
from csvToListOfStings import csvToStringList
import helpers
import main
from frontierManagement import moveAndDel


##############################################
# This file is about dealing with the http- status- codes of the http- response
# we get when requesting the resource belonging to the url
##############################################






# this might be the most complicated dictionary of the entire program, but is really useful to get insights
# into which http- status- codes appeared for which url how many times and when or in which sequence they appeared for the domain
# relevant (these are NOT all entries, but there are entries in responseHttpErrorTracker[domain] which are only used by UTEMA 
# (called in handleCodes)) and of no further relevance to you, the reader: The entries of this dictionary have the form
#
# {domain:{"data": [(time, code)], "urlData": {url: {"counters": {code: counter}, "loopList": [(url, code, time),...]}}}
#
# the names here mean:
#       - domain: a valid domain
#       - time: the time at which the code was was registered by codeHandler, or 
#         by handle3xxLoop (in case of the entry in the list in "loopList"-field)
#       - code: the http- status code of the received http - response (in fetchSingleResponse in urlRequestManagement),
#         or "connection failed", if there was no response received
#       - url: an url with domain domain
#       - counter: the number of times this specific http- code was received since requesting the url the first time
responseHttpErrorTracker = {}


# multiplies the delay- time currently stored in main.frontierDict[url]["delay"] by 2, bounded by 3600 s (1 hour)
# input:
#       - url: an url
#       - info: main.frontierDict[url]
def exponentialDelay(url, info):
    '''increases the crawl- delay associated with that url exponentially'''
    domain = helpers.getDomain(url)
    
    if domain:
        # main.frontierDict[url] = info
        
        delay =main.frontierDict[url]["delay"] 
        if delay > 3600:
            delay = 3600
        else:
            delay = random.uniform(delay*2/1.4, delay*2)
            
        main.frontierDict[url]["delay"] = delay
        main.frontier[url] = time.time() + delay
        if domain in main.domainDelaysFrontier:
            if main.frontierDict[url]["delay"] < main.domainDelaysFrontier[domain]:
                main.frontier[url] = time.time() + main.domainDelaysFrontier[domain]
                main.frontierDict[url]["delay"] = main.domainDelaysFrontier[domain]
        
    
        
          
#input:
#        - location, code: see fetchSingleResponse in urlRequestManagement.py
#        - info: main.frontierDict[url]
#        - responseHttpErrorTracker: responseHttpErrorTracker
#        - retry: The retry- value as returned by retry from helpers.py 
#        - noHandleCodes: If this is True, then codeHandler is not called in the function body and None is returned
#          (used in 3.xx loop)
# output: 
#        - [<Boolean>,newUrl], where the boolean is True if and only if the value of code was of form 2.xx
#          newUrl is a url, which might be different than url, in case a redirection happened (code was of form 3.xx)
#          or None in case of noHandleCodes

# remark: It is probably hard to understand all the different entries of responseHttpErrorTracker here,
#         by just looking at the function body: Just know that responseHttpErrorTracker stores information
#         realted to the http- status- codes of the urls or even the domain, for more information 
#         see the comment above responseHttpErrorTracker above
def statusCodesHandler(url, location, code, info, retry, noHandleCodes=False):
    
    '''writes the documentation of the status_code into responseHttpErrorTracker, further decides
    if there were errors or if there was a redirect'''
    
    
    
    # for the question if it makes sense to disallow a whole domain
    # we calculate an UTEMA- weighted average, that is what the sample- value is for
    sample = 0.25
    domain = helpers.getDomain(url)

    time_ = time.time()
    
    if location:
        location = urljoin(url, location)
    
    # in order to see why it makes sense to handle this case this 
    # way one must realise, that the return value of statusCodesHandler is
    # handleCodes(url, code, location, info)
    if not domain:
        return [False, url]
    if domain not in responseHttpErrorTracker:
        responseHttpErrorTracker[domain] = {"data": [], "urlData":{}}
    if url not in responseHttpErrorTracker[domain]["urlData"]:
        responseHttpErrorTracker[domain]["urlData"][url] = {"counters": {}, "loopList":[]}
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
            
        
    

    if noHandleCodes:
        return None
    result = handleCodes(url, code, location, info)
    if retry:
        # if for whatever reason there was a retry- value received in the http- response (in fetchSingleResponse in urlRequestManagement)
        # we respect it, and thus need to re-schedule the url in the main.frontier accordingly
        main.frontier[url] = main.frontier[url]+ retry
    
    return result
    
        



# detects if a URL is the fifth entry in a chain 
# of reroutes (3.xx- http- status- codes with location- field non- empty). If this is the case, all the URLs in the list get
# taken from the main.frontier and the first url of the list is disallowed
# input:
#       - location: The new url, in case of a redirect
#       - url: the current url 
#       - code: the http- statuscode from the request regarding url in fetchSingleResponse in urlRequestManagement.py
#
# output:
#       - returns [Boolean, newURL], where Boolean is False, if and only if location is the fifth url in a reroute- loop
#         newUrl is here either location, in kind of location non- empty or url
# REQUIREMENTS: location and url need to be absolute and not relative urls
def handle3xxLoop(url,location, code):
    '''handles reroutes (i.e. 3.xx http- status- codes)'''
    time_ = time.time()
    domain = helpers.getDomain(url)
    newUrl = url
    values = [True, url]
    
    if not domain:
        raise main.Error(f'''T {url}" has no recognizable domain,, but this should have been detected much 
                    earlier in the call hierarchy!''')
    
    # if 299< code or code > 400:
    #     return values

    if location:
        newUrl = location
        newDomain = helpers.getDomain(newUrl)
        values[1] = newUrl
        # if this is no domain, leave values[0] as True, the error will then be caught by readFrontier later on
        # after the urls has been being written back in the main.frontier, the http request will report none (if the domain was not valid,
        # the url also mustn't be)
        if newDomain:
            statusCodesHandler(newUrl, None, None, None, None, noHandleCodes= True)
            loopList = responseHttpErrorTracker[domain]["urldata"][url]["loopList"]
            loopList.append((newUrl, code, time_))
            
            if (len(responseHttpErrorTracker[newDomain]["urldata"][newUrl]["looplist"]) <
                        len(loopList)+1):
                responseHttpErrorTracker[newDomain]["urldata"][newUrl]["looplist"] = loopList
                
            
            if len(loopList) == 5:
                moveAndDel(url, "loop")
                values[0] = False
            return values
    # use this case for the case that for some reason there is no Location in the http - response of url, even thoug its status_code is 3.xx
    else:
            responseHttpErrorTracker[domain]["urlData"][url]["loopList"]= [(url,code)]
            
    return values






#handles the possible different Status_codes of a url- request, for more details see the comments in the function body
# arguments:    
#               url: the url for which we received a http- response with status_code code
#               code:  status code of the http- response of url (fetchSingleRespnse in urlRequestManagement.py)
#               location: the new url in case of a redirect (3.xx code)
#               info: the content of main.frontierDict[url]
# output:
#          [<Boolean>,newUrl], where the boolean is True if and only if the value of code was of form 2.xx
#          newUrl is a url, which might be different than url, in case a redirection happened (code was of form 3.xx)
#
def handleCodes(url, code, location, info):
    domain = helpers.getDomain(url)
    values = [False, url]
    
    
    counter = responseHttpErrorTracker[domain]["urlData"][url]["counters"] [str(code)]
    
    if not domain:
        return values
      
    # now we just decide what happens at which code by case- distinction
    
    # this is the case if no http- response at all was received
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
        
    # this is the case if we get a redirect http- response
    elif 299<code<400:
        values[0], url = handle3xxLoop(url,location, code)
        
        if (not values[0]):
            moveAndDel(url, "loop")
            sample = 1
        else:
            sample = 0
                
    # this is the case if for some reason our request was malformed, for example its another content
    # type then our allowed ones (see headers in urlRequestManagement.py)
    elif code == 400:
        if counter == 3:
             moveAndDel(url, "counter")
            
        else:
            exponentialDelay(url, info)
        
        sample = 1
    
    # this is the case if for some reason our client is either not allowed or can't access the site of the url
    elif 400 < code < 500 and code != 429:
        if counter == 2:
               moveAndDel(url, "counter")
        else:
            exponentialDelay(url, info)
            
        sample = 1
            
    # this is the case if the server is overloaded    
    elif code == 429: 
        exponentialDelay(url, info)
        
        if counter == 10:
              moveAndDel(url, "counter")
        sample = 0.5
       
    # this is the case  if there was a server error we consider very severe
    elif 499 < code < 507 or code == 599:
        exponentialDelay(url, info) 
        
        if counter == 5:
               moveAndDel(url, "counter")
            
        sample = 1
    # this is the case if there was a server error we consider less severe  
    elif 506 < code < 510:
        if counter == 3:
               moveAndDel(url, "counter")
            
        else:

            main.frontierDict[url] = info
            info["delay"] = 3600
            main.frontier[url] = main.frontier[url] + 3600
            if main.domainDelaysFrontier[domain]['delay'] > main.frontier[url]:
                main.frontier[url] = main.domainDelaysFrontier[domain]
                
        sample = 0.75
    # all other http status-codes that were not covered until now 
    else:
        if counter == 3:
              moveAndDel(url, "counter")
        sample = 0.4
    if url in responseHttpErrorTracker[domain]:
        
        # max UTEMA - average (weighted average) of bad requests we
        # accept. This considers the times the last http- responses were received as well as the weight (sample) we assigned 
        # to the different status_codes. If this threshold is reached, we assume that crawling on this server does not make
        # sense and we consider it disalllowed (done in moveAndDel), we suspect (temporary) blocking
        if (UTEMA(domain, sample, responseHttpErrorTracker) > 3 and responseHttpErrorTracker[domain]["N_last"] >= 3):
            # in this case, we disallow the whole domain
            moveAndDel(url, "average")
            
    return values          
           