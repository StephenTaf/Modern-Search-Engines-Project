from bs4 import BeautifulSoup
import lxml
import re

def is_useful_soup(soup):
    """Check if parsed soup contains meaningful structure or text."""
    return soup.find() is not None and len(soup.get_text(strip=True)) > 0

def parseText(text, contentType):
    # Try XML first if content-type or content suggests it
    is_xml_hint = (
        "xml" in contentType or
        text.strip().startswith("<?xml") or
        "<rss" in text or "<feed" in text
    )

    if is_xml_hint:
        soup = BeautifulSoup(text, "xml")
        if is_useful_soup(soup):
            return soup.get_text()

    # Fallback to HTML
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()



