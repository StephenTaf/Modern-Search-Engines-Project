
import databaseManagement
from requests.adapters import HTTPAdapter
import time
import matplotlib.pyplot as plt
from heapdict import heapdict
import threading 
from databaseManagement import (store, load, storeCache, findDisallowedUrl, readUrlInfo, printNumberOfUrlsStored 
     ,updateTableEntry, closeCrawlerDB)
import helpers
from frontierManagement import frontierInit, manageFrontierRead
import frontierManagement
import statusCodeManagement
# in order to be able to raise customed- errors
class Error(Exception):
    pass






# just needed to manage the interactions between the the main_thread running the crawler and the input_thread running
# the inputReaction. The running- field acts as a switch in this, meaning once it is set to false, inputReaction as
# well as the crawler break out of their respective while- loops
stopEvent = threading.Event()


# this only is there for capturing the input- command "stop", which can be entered after "Wait for input..." is displayed.
# if "stop" is entered then into the terminal and enter is hit, the crawler will stop its crawling process and store the caches,
# including frontierManagement.frontier and frontierDict and then the program will end. One can see, that the input worked, if "shut- down in progress"
# is being displayed in the terminal
def inputReaction():
    '''if "stop" is entered, this will start the program- shutdown'''
    while not stopEvent.is_set():
        print("[debug] Waiting for input...")
        cmd = input()
        print("[debug] Received input:", cmd)
        if cmd == "stop":
            print("[shut- down in progress")
            # sets the stop- event in order to break this while- loop as well as the while- loop
            # in the crawler- function
            stopEvent.set()
            running = False
            print("the crawler now stores the frontier, load the caches into the databases and won't read from the frontier any more. Furthermore, after this is done, the crawler function call will end")
    
    
    
    
    
# this function is just used for printing useful statistics while the crawler- function is in progress (called every 10th
# round of the crawling loop and then once after the loop stopped 
def printInfo():
    print(f"the actual number of cachedUrls: {len(frontierManagement.cachedUrls)}")
    print(f"the actual number of tracked websites (because of http- statuscode): {len(statusCodeManagement.responseHttpErrorTracker)}")
    print(f"the size of the frontier: {len(frontierManagement.frontier)}")
    print(f"the actual number disallowedUrls: {len(frontierManagement.disallowedURLCache)}")
    print(f"the actual number disallowedDomains: {len(frontierManagement.disallowedDomainsCache)}")
    printNumberOfUrlsStored()
    for index in range(min(10, len(frontierManagement.frontier)-1)):
                if frontierManagement.frontier != []:
                    url = list(frontierManagement.frontier)[-(index-1)]
                    if helpers.getDomain(url) in statusCodeManagement.responseHttpErrorTracker:
                        print(f'''In the domain {helpers.getDomain(url)} these were the last status_codes at the times: {[a[1] for a in statusCodeManagement.responseHttpErrorTracker[helpers.getDomain(url)]["data"]]}''')
                        print("--------------------------")
    print("---------------------------------------------------")
    
    
    
# input:
#        - a list of urls whit which are used to initalise the frontierManagement.frontier
# 
# What this function does:
 # this is the heart of our crawler, the crawler- function. After loading the stored data (frontierManagement.frontier, frontierDict etc.)
 # and initialising the frontierManagement.frontier with the seed, it manages the crawling- process by basically executing a
 # while- loop which calls databaseManagement.storeCache in order to 
 # check if the cachedUrls dictionary has 1000 entries, and if so it is being stored and then the cachedUrls dictionary is emptied,
 # after that frontierManagement.manageFrontierRead iis being called. This loop runs until either the stopEvent is set,
 # or the frontierManagement.frontier is empty.
 # If this is the case it stores the cachedUrls, the frontierManagement.frontier, the frontierDict and additional information in the other caches into storage
def crawler(lst):#inputThread):
    '''manages all of the crawling- process, including loading data into the caches in the beginning and storage'''
    # IMPORTANT: Activate this in order to load the earlier frontierManagement.frontier from the database
    print("Input not yet available, please wait!")
           
    (frontierManagement.frontier, frontierManagement.frontierDict, frontierManagement.domainDelaysFrontier,
    frontierManagement.disallowedURLCache, frontierManagement.disallowedDomainsCache, statusCodeManagement.responseHttpErrorTracker) = load()
    frontierInit(lst)
    counter = 0
    
    # starts the inputReaction- thread
    threading.Thread(target=inputReaction, daemon=True).start()
    
    l = len(frontierManagement.frontier)
    
    print("Initial l =", l)
    print("stopEvent.is_set() =", stopEvent.is_set())
    while l !=0 and not stopEvent.is_set():
        # IMPORTANT: Want to store the cachedURLs into the dabase, after a certain amount of entries are reached
        # (currently 20 000, which should be doable by every system with 4GB RAM (still usable during it,
        # takes accordig to chatGPT only 1 GB ram))
        if frontierManagement.frontier.peekitem()[1] < time.time():
            storeCache(frontierManagement.cachedUrls)
            lastCachedUrl = manageFrontierRead()
            counter +=1
            l = len(frontierManagement.frontier) 
                
        if l == 0 or stopEvent.is_set():
            print(f"last storedUrl: {lastCachedUrl}")
            break
        if len(frontierManagement.frontier)!= len(frontierManagement.frontierDict):
            print(f"urls only contained in frontierDict, but not infrontier: {[a for a in frontierManagement.frontierDict if a not in frontierManagement.frontier]}")
            raise Error("the frontier does not have the same lengt as the frontierDict!")
        
    
        if counter % 10 == 0:
            counter = 0
            printInfo()

    # sets the stop -event in order to close the inputReaction thread by breaking the while- loop there as well        
    stopEvent.set()  
    printInfo()
        

    store(frontierManagement.frontier, frontierManagement.frontierDict, frontierManagement.domainDelaysFrontier, frontierManagement.disallowedURLCache, 
          frontierManagement.disallowedDomainsCache, frontierManagement.cachedUrls, helpers.strangeUrls,
         statusCodeManagement.responseHttpErrorTracker)
    
# this calls the crawler, and runs it such that frontierManagement.frontierInit receives the list lst in order to initialise the frontier with
# the urls in lst. After the crawler is run for completion sake, it closes the connection to the CrawlerDB.duckdb database that was
#  opened in databaseManagement.py
def runCrawler(lst):
    '''calls the crawler, and ensures it only does so on the main thread'''
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
