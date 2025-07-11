import CrawlerHelpers

 # this is the information REGARDING THE GIVEN URL that we are allowed to use for the calculation
 # of the relevance score with regard to Tübingen and english pages
 # you can have a look at urlFrontier and 
 # the comment about it in the CrawlerHelpers.py
 # information = CrawlerHelpers.urlFrontier[url]
 
 #------------------------------
 # Online metrics (use them while the crawler is running)
 
 # in doubt they should decide for crawling, not against it
 #--------------------------------

#incoming Score is the sum of all the incoming tueEngScores
# this should be only used as a deciding criteria for the metric, in case
# that the url- and text- score together would not be enough to consider
# the page as relevant for our database, it should only lead to a positive decision
# if the sum of the score of the incoming links is very high, otherwise the site should
# not be crawled
def incomingScore(incomingLinks):

    pass

#the naming of the url can maybe also influence our tueEngScore a tiny bit in the end
# in the metric this should be weighted most together with the textScore
def urlScore (url):
    pass


# ------> MOST IMPORTANT FOR NOW: TODO
# the text content needs to be analysed in order to calculate a score for it to 
# determine how likely it is that it is in english and about tübingen
# in the metric this should be weighted most together with the urlScore
def textScore(text):
    pass


# This is the final metric that defines the relevance score for a given url (this 
# only gets FULL urls, not relative ones). The relevance score is the tueEngScore,
# it gets the url and extracts the relevant information. The relevance score should
# be between 0 and 1 (we interpret it as a probability)


# ------> MOST IMPORTANT FOR NOW: TODO
# NOTE: This should respect that for a certain linking- depth (5 maybe?) on a domain the urls of this domain should not be fetched, further it should combine the scores above (weighted differently somehow)
def metric(information):
    pass
    
    


 #--------------------------------
# for the offline processing, after the crawling is done:
 #--------------------------------
 
 
# NOTE: this metric should now take the minimal linking-depth into account and use it 
# as a variable in the actual weighting (the idea is: If a website is reached only
# through a lot of links on the same domain, and we were unsure that the website really relates to Tübingen and is in english, then this website very likely is not
# relevant to our database). Note that the way the linking-depth is defined (the minimum of chained links on the same domain to reach the page) it cannot be approximated at runtime. Therefore we need to do this post- processing
def OfflineMetric(information):
    
    pass


# further ideas: 
# - could use the sum of the score of the outgoing links in the post- processing to
# determine how important a url, where we doubt its connection to tübingen fiven the
# metric, actually is.