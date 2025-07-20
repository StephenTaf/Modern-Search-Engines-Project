import re

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



# input:
#       - url: the url whose domain we want returned
#       - strangeUrls: The list in which we want to store urls which don't obey the domain- rule 
# (www. ... until, not including "/" is reached (if it exists)), given a
# full (not a relative) url as a string
def getDomain(url, strangeUrls = None, useStrangeUrls = False):
    '''extracts the domain from a given url'''
     # this extracts the domain- name from the url
    domain = re.findall("//([^/:]+)", url)
    if useStrangeUrls:
        if len(domain)<1:
            #f"This is not a domain. The url before was: {url}")
            strangeUrls.append(url)
            return None
        
    return domain[0]