from scoring import ContentScorer
from config import CrawlerConfig
from text_processor import TextProcessor
import CrawlerHelpers


_config = CrawlerConfig()
_tp = TextProcessor()
_scorer = ContentScorer(_config)

def _get_clean_text(text):
    """Stringify and clean text for scoring (supports str or BeautifulSoup)."""
    if hasattr(text, "get_text"):
        text = text.get_text(separator=" ", strip=True)
    return _tp.extract_text(str(text))

def metric(information):
    url = information.get("url", "")
    text = information.get("text", "")
    incoming = information.get("incoming", [])
    linking_depth = information.get("linkingDepth", 0)
    domain_linking_depth = information.get("domainLinkingDepth", linking_depth)
    #I see you have  penalized the path_depth at 6. I think it's better to add it to config instead of hardcoding it. 
    # Config-driven cutoff
    if linking_depth > 7 or domain_linking_depth > 7:
       information["tueEngScore"] = 0.0
       return 0.0

    score = _scorer.calculate_final_score(
        url=url,
        text=_get_clean_text(text),
        incoming_links=incoming,
        linking_depth=linking_depth
    )
    information["tueEngScore"] = score
    return score

def OfflineMetric(information):
    min_depth = information.get("minimalLinkingDepth", information.get("linkingDepth", 0))
    score = _scorer.calculate_final_score(
        url=information.get("url", ""),
        text=_get_clean_text(information.get("text", "")),
        incoming_links=information.get("incoming", []),
        linking_depth=min_depth
    )
    information["tueEngScore"] = score
    return score
