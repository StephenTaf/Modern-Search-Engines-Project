from bs4 import BeautifulSoup, Comment
from typing import Tuple, Optional, Dict, List, Any
import re
from urllib.parse import urljoin
import helpers
import html
from bs4 import XMLParsedAsHTMLWarning
import warnings

# input:
#       - html_text: the raw text contained in the content of some http- response, 
#                    note, that it is empty if nothing is received
#
#       - base_url: the url which is needed for extractUrls
#
# output:
#       - raw_text: The text we use for the indexer later on
#       - title: the title, if there is any in the raw_text, otherwise ""
#       - urlList: the list of all clickable urls we found in raw_text
#
# remark: For parts of this function an LLM was used, however the style here is also not consistent, 
#         because one group- member wrote the basis function and another edited it afterwards 
def parseTextAndFetchUrls(html_text, base_url) -> Tuple[str, str, List[str]]:
    """
    Optimized HTML parsing that uses lxml parser for better speed and 
    reduces the complexity of content extraction while maintaining quality.
    
    Args:
        crawler_response: Dictionary containing response data
    
    Returns:
        Tuple[str, str]: (cleaned_content, title)
    """
    def _remove_unwanted_elements_fast(soup: BeautifulSoup) -> None:
        """Fast removal of unwanted elements - reduced selector list."""
        # Minimal but effective unwanted element removal
        unwanted_selectors = [
            # Core navigation and layout
            'nav', 'header', 'footer', 'aside',
            # Scripts and styles
            'script', 'style', 'noscript',
            # Ads and social
            '.ad', '.ads', '.social', '.share',
            # Comments and metadata
            '.comment', '.meta', '.breadcrumb'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
    
    def _identify_main_content_fast(soup: BeautifulSoup) -> BeautifulSoup:
        """Fast main content identification."""
        # Priority order for main content
        for selector in ['main', '[role="main"]', 'article', '.content', '#content']:
            element = soup.select_one(selector)
            if element:
                return element
        
        # Fallback to body
        return soup.find('body') or soup
    
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    # Use lxml for faster parsing
    try:
        soup = BeautifulSoup(html_text, 'lxml')
    except:
        # Fallback to html.parser
        soup = BeautifulSoup(html_text, 'html.parser')
    
    # Extract title
    title = "Untitled"
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text(strip=True)
    elif soup.find('h1'):
        title = soup.find('h1').get_text(strip=True)
    
    # Fast unwanted element removal
    _remove_unwanted_elements_fast(soup)
    
    # Fast main content identification
    main_content = _identify_main_content_fast(soup)
    
    # Extract text
    if main_content:
        raw_text = main_content.get_text(separator='\n', strip=True)
    else:
        raw_text = soup.get_text(separator='\n', strip=True)
    
    # Basic text cleaning
    if raw_text:
        # Replace multiple whitespace with single space/newlines
        raw_text = re.sub(r'\s+', ' ', raw_text)
        raw_text = re.sub(r' \n ', '\n', raw_text)
        raw_text = raw_text.strip()
    urlList = extractUrls(soup, base_url)
    
    return raw_text, title, urlList
        
        
        
 # given the body of a html - page (i.e. the requests(url.text)) as a beautiful soup- structure
# (not the text- body of an error- http - response (a response with code not of form 2.xx)),
# we extract all the meaningful (clickable) urls we can find from this soup
#input:
#       - soup: The soup structure that beatiful soupe produces
#       - base_url: needed in order to calculate the full url for the output- list, in case the given urls are only relative
#output:
#       - a list of the urls that were found
# chatGPT wrote some parts of this: Pro: also works with xml, which the former function (commented out) does not
def extractUrls(soup, base_url):
    '''extracts the urls from the given soup, if there are any clickkable ones'''

    urls = set()
    
    if not soup:
        return []

    # --- HTML: clickable hrefs ---
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.startswith(("http", "/")):
            try:
                urls.add(urljoin(base_url, href))
            except:
                pass

    # --- XML: link tags and enclosures ---
    for tag in soup.find_all(["link", "enclosure"]):
        # Handle both: <link href="..."/> and <link>https://...</link>
        url = tag.get("href") or tag.get("url") or tag.string
        if url and url.strip().startswith(("http", "/")):
            try:
                urls.add(urljoin(base_url, url.strip()))

            except ValueError:
                helpers.strangeUrls.append(url.strip())

    # Unescape HTML entities (e.g. &amp;)
    urls = [html.unescape(u) for u in urls]
    # we don't wanit urls linking to sitemaps, because we decided to 
    # crawl site- structure aware (we store the depth of a link inside a site in cachedUrls[url]["linkingDepth"])
    finalUrls = [url for url in urls if not helpers.isSitemapUrl(url)]
    return finalUrls