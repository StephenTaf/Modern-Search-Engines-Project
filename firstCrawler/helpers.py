import re
from bs4 import BeautifulSoup
import re
import warnings
from requests.adapters import HTTPAdapter
import bisect #module for binary search
import matplotlib.pyplot as plt
import re
from datetime import datetime, timezone
from dateutil.parser import parse
from urllib.parse import urljoin
import html
from seed import Seed as seed
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import warnings


##############################################
# This file really just contains small helper functions used by the other files in the folder
##############################################


# here everything catched by helpers.getDomain lands, that does not have a valid domain- prefix (this means that it is not a real url,
# at least presumably), but in our current (and regarding the project final) crawler version we don't use it, also conatins urls
# for which urljoin from urllib.parse does not work
strangeUrls = []

# arguments:    
#               lst: is a list of lexicographically ordererd items
#               item: is an item that is to be inserted into the list
# return value: 
#               list of lexicographically ordered items where item has been inserted
def addItem(lst, item):
    '''adds an item to analready lexicographically ordered list lst'''
    
    i = bisect.bisect_left(lst, item)

    if i < len(lst)-1:
        if item != lst[i+1]:
            lst.insert(i+1, item)
    else:
        lst.insert(i+1, item)

    return lst

# used in order to exclude urls that contain sitemaps, since we want to crawl 
# "structure- aware" on each domain
siteMapPatterns = [
    r"sitemap.*\.xml$",       # sitemap.xml, sitemap-1.xml, sitemap_news.xml
    r"/sitemap/?$",           # /sitemap or /sitemap/
    r"sitemap_index.*\.xml$", # sitemap_index.xml
]

# we really don't want to crawl sitemaps, because if we do we might loose the actual structure of the website,
# which we will use for our scoring system
# argument:
#           - url: an url
# output:
#       returns True, if the url probably links to a site which stores a sitemap, False otherwise
def isSitemapUrl(url: str) -> bool:
    url = url.lower()
    return any(re.search(p, url) for p in siteMapPatterns)



# input:
#       - url: the url whose domain we want returned
#       - strangeUrls: The list in which we want to store urls which don't obey the domain- rule 
#         (www. ... until, not including "/" is reached (if it exists)), given a
#         full (not a relative) url as a string, if this is not None, and the given url does not have a domain (i.e., is not an url after all)
#         this url gets stored in strange Urls
# output:
#       - domain of the given url, if the url was not a url after all None is returned
def getDomain(url, strangeUrls = None):
    '''extracts the domain from a given url'''
    
     # this extracts the domain- name from the url
    domain = re.findall("//([^/:]+)", url)
    if strangeUrls != None:
        if len(domain)<1:
            #f"This is not a domain. The url before was: {url}")
            strangeUrls.append(url)
            return None
       
    return domain[0]




# Given a list of (relative) urls and a comparison url, which one is the 
# longest match?
def longestMatch(urlList, comparisonURL):
    ''' returns the url which is the longestMatch'''
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


        
        

# used to read the retry-after header from response.get(<url>).headers (see statusCodeHandler in statusCodeManagement.py)
def retry(value):     
    '''converts the retry- value into unix-time''' 
    if value :
        if value.isdigit():
            value = int(value)
            
        else:
            # first converts the time of the crawler and the time of the retry-value in the same zone, then converts it to seconds and then calculates
            # how many seconds the retry- date is in the future
            value = (parse(value).astimezone(timezone.utc)        
            .timestamp())                    
            
    return value

      #------------
# given the body of a html - page (i.e. the requests(url.text)) as a beautiful soup- structure
# (not the text- body of an error- http - response (a response with code not of form 2.xx)),
# we extract all the meaningful (clickable) urls we can find from this soup
#input:
#       - soup: The soup structure that beatiful soupe produces
#       - base_url: needed in order to calculate the full url for the output- list, in case the given urls are only relative
#output:
#       - a list of the urls that were found
# chatGPT wrote some parts of this: Pro: also works with xml, which the former function (commented out) does not
def extractUrls(soup, base_url,):
    '''extracts the urls from the given soup, if there are any clickkable ones'''

    urls = set()
    
    if not soup:
        return []

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

# used to extract from a given text_ and content type (the content type as stated in the body of the http- response of a url- request)
# as well as the urls from the given text
# , if the contentType is either html or xml, it returns  the human- readible content (text) and the title, as well as 
# the for our purpose relevant urls of this page (the clickable ones) as a tuple (text, title, urlList).
def parseTextAndFetchUrls(text_, contentType, base_url):
    '''extracts text and title'''
    soup = None
    text = ""
    title = ""
    xmlContent = False
    htmlContent = False

    if contentType:
        xmlContent = "xml" in contentType
        htmlContent = "html" in contentType
    
        
    # this is in order for Beautiful soup not to give warnings, if the given text is neither xml nor html 
    warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
    if xmlContent or text_.strip().startswith("<?xml"):
        soup = BeautifulSoup(text_, "xml")
    elif htmlContent or "<html" in text_.lower():
        soup = BeautifulSoup(text_, "html.parser")

    if soup:
        #this part was written by ChatGPT
        result = " ".join(
            t.get_text(" ", strip=True)
            for t in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "article"])
        )
        if soup.title:
            title = soup.title.string
    urls = extractUrls(soup, base_url)   
    
    return (text,title, urls)