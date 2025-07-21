
import requests
from requests.adapters import HTTPAdapter
import httpx
import asyncio
import helpers
import robotsTxtManagement 
from urllib.parse import urljoin
##############################################
# This file is about fetching the information needed by our crawler for a given number of the frontier- URLS
# asynchronically from the internet
##############################################

headers = ({ 
    # name of our crawler
    "User-Agent": "MSEprojectCrawler",
    
    #We don't have a webpage for our crawler, so a personal e- mail Address needs to suffice
    "From": "poncho.prime-3y@icloud.com",
    
    # the different formats our crawler accepts and the preferences
    "Accept": "text/html,application/xhtml+xml q= 0.9,application/xml;q=0.8,*/*;q=0.7",
    
    # the languages our crawler accepts
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    
    #keeping the connection alive, so we do not need a new TCP handshake for each request
    "Connection": "keep-alive"})



# arguments:
#           - url: The url for which we want to fetch the information from the internet
#           - client: The name of the httpx.AsyncClient- client
#   output :
#           - a dictionary containing the fetched information about the url. There are two possibilites which fields are contained in 
#             the dictionary. For more information: see the function- body
async def fetchSingleResponse(client,url):
    '''fetches the information for a single- url'''
    
    # this is being returned if there was no response to the http- request for this url (response, see below) 
    urlDict = {
            "url": url,
            "responded": False
        }
    robot = None
    try:
        response = await client.get(url)
    
        try:
            # doing this will save us 1 http- request per call of an url of a 
            # domain we called earlier on in the future -> major time- saving
            domain = helpers.getDomain(url)
            if domain and domain in robotsTxtManagement.robotsTxtInfos:
                robot = None
            else:
                robotResponse = await client.get(urljoin(url, "/robots.txt"))
                robot = robotResponse.text
                
        except:
            pass
    
            
        # this is returned, if a http- response to the response- request was received
        return {
            "url": url,
            "text": response.text,
            #this is empty, if no response for robotResponse (requesting the robots.txt- url) was received
            "robot": robot,
            # this is the http- status- code of response, becomes very important later on for statusCodeManagement
            "code": response.status_code,
            
            # this will be used later on for reading the human- readible part of the text as well as the title out (see parse_text in helpers.py) 
            "contentType": response.headers.get("Content-Type"),
            # this is the url of another site, is used for redirects (http- status- codes of form 3.xx),
            # is needed for detection of redirect- loops as well as following normal redirects (see handle3xxLoop in statusCodeManagement)
            "location": response.headers.get("Location"),
            # this is a given date or time- value until which crawling is denied, this is used for example in 5.xx headers,
            # we use it in frontierRead in frontierManagement.py
            "retry" : response.headers.get("Retry-Value"),
            # if a http- response was received by client.get(url) this is true, otherwise it is false (see start of function body)
            "responded": True
        }
    except:
         return urlDict
     
     
# 
# arguments: 
#           - lstOfUrls: list of urls it is given (note that all domains of urls in this list are different by construction of the input, where fetchResponses is calles,
#           i.e. by manageFrontierread in frontierManagement)
#
# output:   a dictionary where each field stores the dictionary returned by fetchSingleResponse, for the respective url for all urls in lstOfUrls

#chatGPT did help write this function        
async def fetchResponses(lstOfUrls):
    '''asynchronically fetches the information per url for a list of given urls'''
    timeout = httpx.Timeout(1.5) 
    async with httpx.AsyncClient(timeout=timeout, headers= headers, follow_redirects= False ) as client:
        tasks = [fetchSingleResponse(client, url) for url in lstOfUrls]
        responses = await asyncio.gather(*tasks)
        return responses

