import CrawlerHelpers

import pytest
import time

import CrawlerHelpers
from CrawlerHelpers import errorDomain


delay = 1
urlFrontier = CrawlerHelpers.urlFrontier

# gets a codesList and starting from this 
def fillResponses(codesList):
    for a in codesList:
        url = f"http://www.{a[0]}.com/fakeUrl{a[0],a[1]}"
        domain = CrawlerHelpers.getDomain(url)
        urlFrontier[url] = {"delay":1}                
                
        responses = {}       
        responses[f"fakeUrl{a[0],a[1]}"]= {}
        responses[f"fakeUrl{a[0],a[1]}"]["code"] = a[0]
            
        
        
    


# function that creates a filling for a full test of the
# urlFrontier- responseHttp- pipeline
def test_(number):
    #checking if 
    urlFrontier["url1"]
    