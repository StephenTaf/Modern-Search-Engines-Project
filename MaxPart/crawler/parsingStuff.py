from bs4 import BeautifulSoup
import requests
import lxml
import re
import warnings


def parseText(text_, contentType):
    soup = None
    text = ""
    title = ""
    xmlContent = False
    htmlContent = False

    if contentType:
        xmlContent = "xml" in contentType
        htmlContent = "html" in contentType
        
    if xmlContent or text_.strip().startswith("<?xml"):
        soup = BeautifulSoup(text_, "xml")
    elif htmlContent or "<html" in text_.lower():
        soup = BeautifulSoup(text_, "html.parser")

    if soup:
        result = " ".join(
            t.get_text(" ", strip=True)
            for t in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "article"])
        )
        if soup.title:
            title = soup.title.string
    return (text,title)

# was just for testing:
# url = "https://whatsdavedoing.com"
# response = requests.get(url, timeout=10)
# text = parseText(response.text, response.headers.get("Content-Type", ""))
# print(text[:1000])


