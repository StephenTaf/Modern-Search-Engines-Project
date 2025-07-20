import re
import helpers

##############################################
# This file is all about reading a given robots.txt- text- file for a given URL and deciding
# if the URL is allowed to be crawled and what is the minimum acceptable crawling- delay.
##############################################

# contains entries of form <domain-name>:
# a dictionary with entries of the form 
#       <domain>: {"allowed": <list of allowed Urls>, "forbidden": <list of disallowed urls>, "delay": <crawler- delay>}
# ,where: domain is the domain- part of some URL,  "allowed"-field stores the (sub-) urls our crawler is allowed to crawl, 
# "forbidden"-field stores the (sub-) urls which are not allowed to be 
# accessed by our crawler, "delay"-field stores the crawler delay, a double digit, that specifies how many seconds our crawler has to wait at least
robotsTxtInfos = {}

# arguments:
#           - robotTxt: The text- content stored an the robot.txt site of a domain, or None, if it doesn't exist
# output:
#           - an entry of the form {"allowed": <list of allowed Urls>, "forbidden": <list of disallowed urls>, "delay": <crawler- delay>},
#             which later gets stored in robotsTxtInfos

def extractTheRobotsFile(robotText): 
    ''' returns the relevant information of the robots txt in a dictionary of the form
    {"allowed": <list of allowed Urls>, "forbidden": <list of disallowed urls>, "delay": <crawler- delay>}'''
    
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
            agentBoxStart = item1.startswith("user-agent:*") or item1.startswith("user-agent:mseprojectcrawler")

        if agentBoxStart & (rulesStart == False):
            if index != len(textList):
                if not textList1[index].startswith("user-agent"):
                    rulesStart = True

                    
        if agentBoxStart & rulesStart:
            indexOfColon = item.find(":")
            key = item1[0:indexOfColon]
            if key == "allow":
                helpers.addItem(robotsDictionary["allowed"], item[indexOfColon+1:])
            elif key == "disallow":
                helpers.addItem(robotsDictionary["forbidden"], item[indexOfColon+1:])
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
                #Sometimes there is extra- info in the file since crawlers usually just ignore other
                # then the mentioned fields we don't need this
                # raise ValueError(f"Somehow the implemented rules are not sufficient, there is a word {key} at the beginning of the file")
                pass

    return robotsDictionary


# arguments:
#           - robotText: The text- content stored an the robot.txt site of a domain, or None, if it doesn't exist
#           - url: The url of a site whose domain is associated to the robotText (if it exists)
#           - domainDelaysFrontier: shas to be exactly the structure domainDelaysFrontier from the main.py file
# output:
#           - a tuple of form (<number>, <Boolean>), where the Boolean states if crawling is allowed on this url according to
#             the robots.txt (if it exists) and the nunber is the number of seconds of the required crawl- delay for the url

def robotsTxtCheck(url, robotText, domainDelaysFrontier):
    '''checks robots.txt if crawling is allowed for that url and what the required crawl- dealy is.'''
    domain = helpers.getDomain(url)
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
        # we suppose the robotsTxt does not exist, if we could not fetch it on first try
        # therefore we use this dummy- entry for future- refernces to the robots.txt of this 
        # url. 1.5 seconds of crawling- delay is very polite for todays conditions
            robotsTxtInfos[domain] = {"allowed":[], "forbidden": [], "delay": 1.5}
            if domain not in domainDelaysFrontier:
                  domainDelaysFrontier[domain] = 1.5
                     
            return (1.5, True)

        robotsTxtInfos[domain] = roboDict
        
    allowedMatch = helpers.longestMatch(roboDict["allowed"], url)
    forbiddenMatch = helpers.longestMatch(roboDict["forbidden"], url)
    
    if allowedMatch > forbiddenMatch or allowedMatch == forbiddenMatch:
        if domain in domainDelaysFrontier:
            domainDelaysFrontier[domain] = max(domainDelaysFrontier[domain], roboDict["delay"])
        else:
            domainDelaysFrontier[domain] = roboDict["delay"]
        value = (roboDict["delay"], True)  
    

    return value
    
    