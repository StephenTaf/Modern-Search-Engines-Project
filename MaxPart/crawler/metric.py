import CrawlerHelpers
import re
from langdetect import detect
from tuebingen_terms import (
    TUEBINGEN_PHRASES, CITY_TERMS, UNIVERSITY_TERMS, FACULTY_TERMS, ACADEMIC_TERMS
)
def incomingScore(incomingLinks):
    """
    Sum of tueEngScores of all incoming links.
    Each element in incomingLinks is a pair: (url, score) or (url, _).
    If score is not available, try to fetch from urlFrontier.
    """
    total = 0.0
    for link in incomingLinks:
        url = link[0]
        score = link[1] if len(link) > 1 and link[1] is not None else \
            (CrawlerHelpers.urlFrontier[url]["tueEngScore"] if url in CrawlerHelpers.urlFrontier else 0.0)
        total += score
    return total

#the naming of the url can maybe also influence our tueEngScore a tiny bit in the end
# in the metric this should be weighted most together with the textScore

def urlScore(url):
    """
     score based on URL keywords.
    """
    url_lc = url.lower()
    score = 0.0

    #Tübingen-relevant keywords
    for keyword in ["tuebingen", "tübingen", "uni-tuebingen", "tue"]:
        if keyword in url_lc:
            score += 0.5
            break
    if "/en/" in url_lc or url_lc.endswith("/en"):
        score += 0.2 
    if ".uni-tuebingen.de" in url_lc:
        score += 0.2
    #deep paths. 
    path_depth = url.count("/")
    if path_depth > 6:
        score -= 0.1 * (path_depth - 6)

    score = max(0.0, min(1.0, score))
    return score


# ------> MOST IMPORTANT FOR NOW: TODO
# the text content needs to be analysed in order to calculate a score for it to 
# determine how likely it is that it is in english and about tübingen
# in the metric this should be weighted most together with the urlScore

# at the top of crawlerMetric.py


# crawlerMetric.py


def compile_regex(term_list):
    return [re.compile(r"\b" + re.escape(term) + r"s?\b", re.IGNORECASE) for term in term_list]

TUEBINGEN_REGEXES = compile_regex(TUEBINGEN_PHRASES)
CITY_REGEXES = compile_regex(CITY_TERMS)
UNIV_REGEXES = compile_regex(UNIVERSITY_TERMS)
FACULTY_REGEXES = compile_regex(FACULTY_TERMS)
ACADEMIC_REGEXES = compile_regex(ACADEMIC_TERMS)

import re
from langdetect import detect

def textScore(text):
    
    raw = text if isinstance(text, str) else str(text)
    lc = raw.lower()
    try:
        lang = detect(raw)
    except Exception:
        en_words = [" the ", " and ", " of ", " to ", " in "]
        en_count = sum(lc.count(w) for w in en_words)
        lang = "en" if en_count > len(lc.split()) / 100 else "unknown"
    if lang != "en":
        return 0.0

    tuebingen_hits = sum(1 for rx in TUEBINGEN_REGEXES if rx.search(lc))
    city_hits = sum(1 for rx in CITY_REGEXES if rx.search(lc))
    faculty_hits = sum(1 for rx in FACULTY_REGEXES if rx.search(lc))
    university_hits = sum(1 for rx in UNIV_REGEXES if rx.search(lc))
    academic_hits = sum(1 for rx in ACADEMIC_REGEXES if rx.search(lc))

    # Slightly higher weights for main signals
    base_score = 0.25 * min(1, tuebingen_hits / 2) + \
                 0.16 * min(1, city_hits / 2) + \
                 0.16 * min(1, university_hits / 2) + \
                 0.11 * min(1, faculty_hits / 2)

    academic_boost = 0.32 * min(1, academic_hits / 3)
    score = base_score + academic_boost

    if tuebingen_hits > 0 and academic_hits > 0:
        score += 0.10  # synergy boost

    if re.search(r"\b(germany|baden-württemberg)\b", lc):
        score += 0.08

    score = max(0.0, min(1.0, score))
    return score



# ------> MOST IMPORTANT FOR NOW: TODO
# NOTE: This should respect that for a certain linking- depth (5 maybe?) on a domain the urls of this domain should not be fetched, further it should combine the scores above (weighted differently somehow)


def metric(information, url):
    """
    normalized relevance score
    """
    text = information["text"]
    incoming = information["incoming"]
    linkingDepth = information["linkingDepth"]
    domainLinkingDepth = information["domainLinkingDepth"]

    # Hard cutoff for very deep pages
    DEPTH_LIMIT = 5
    if linkingDepth > DEPTH_LIMIT or domainLinkingDepth > DEPTH_LIMIT:
        return 0.0

    u_score = urlScore(url)
    t_score = textScore(text)
    in_score = incomingScore(incoming)

    depth_penalty = 1.0 - 0.1 * max(linkingDepth, domainLinkingDepth)
    depth_penalty = max(0.5, depth_penalty)
    normalized_in = min(1.0, in_score / 3.0) 

    #content is important but I will a bit to url and incoming score. 
    
    base_score = (
        0.6 * t_score +
        0.25  * u_score +
        0.1  * normalized_in
    )
    score = base_score * depth_penalty

    if score < 0.4 and normalized_in > 0.8:
        score = min(1.0, score + 0.15)


    return max(0.0, min(1.0, score))

 
# NOTE: this metric should now take the minimal linking-depth into account and use it 
# as a variable in the actual weighting (the idea is: If a website is reached only
# through a lot of links on the same domain, and we were unsure that the website really relates to Tübingen and is in english, then this website very likely is not
# relevant to our database). Note that the way the linking-depth is defined (the minimum of chained links on the same domain to reach the page) it cannot be approximated at runtime. Therefore we need to do this post- processing


def OfflineMetric(information):
    """
    Post-processing metric for final page relevance after crawling is complete.
    """
    url = information["url"]
    text = information["text"]
    incoming = information["incoming"]
    outgoing = information["outgoing"]
    linkingDepth = information["linkingDepth"]
    domainLinkingDepth = information["domainLinkingDepth"]

    t_score = textScore(text)
    u_score = urlScore(url)
    in_score = incomingScore(incoming)

    out_score = 0.0
    max_out = 5  
    out_count = 0
    #if outgoing scores are available later. 
    for out in outgoing:
        out_url = out[0] if isinstance(out, (list, tuple)) else out
        out_score += CrawlerHelpers.urlFrontier.get(out_url, {}).get("tueEngScore", 0.0)
        out_count += 1
    if out_count:
        out_score = min(1.0, out_score / max_out)
    else:
        out_score = 0.0

    max_allowed_depth = 8
    min_depth = min(linkingDepth, domainLinkingDepth)
    depth_penalty = min(0.5, 0.05 * max(0, min_depth - 2))  
    score = (
        0.45 * t_score +
        0.25 * u_score +
        0.15 * min(1.0, in_score / 3.0) +   
        0.15 * out_score
    )

    score *= (1 - depth_penalty)

    if t_score < 0.3 and u_score < 0.3 and min_depth > 6:
        score *= 0.5

    return max(0.0, min(1.0, score))