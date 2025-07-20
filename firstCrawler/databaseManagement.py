import duckdb
import time
import json
import helpers
import copy
from heapdict import heapdict
from collections.abc import Iterable

# in order to be able to raise customed- errors
class Error(Exception):
    pass
#......................................
#all tables which are part of our database
#......................................
crawlerDB = duckdb.connect("crawlerDB.duckdb")

# this table stores the crawled urls together wit additional data
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS urlsDB (
        id BIGINT PRIMARY KEY,
        url TEXT UNIQUE,
        
        -- title is the title extracted from the html/ xml code of the website
        title TEXT,
        
        -- this is the human- readible plain text content
        text TEXT,
        
        -- the Unix- time at which the websites content was last fetched (not last visited!!!) by the crawler,
        lastFetch DOUBLE,
        
        -- this is a list of all urls found on the website (initially we wanted to use 
        -- this in some post- processing (pruning of the dataset) step regarding the webistes, however
        -- at the end we decided against it, since it is a lot of storage (and time-) overhead during crawling)
        -- outgoing TEXT[],
        
        -- this is a list of all urls which the crawler encountered, which link to this website
        -- we only need this, because we want to caclulate the linkingDepth and the domainLinkinking Depth of the websites
        incoming TEXT,
        
        -- the domainLinkingDepth of an url is the number of urls the crawler encountered on a
        -- the shortest path inside the current domain, the crawler took until it encountered this url
        domainLinkingDepth TINYINT,
        
        -- the linking depth is the shortest path in the crawling- graph from the seed list to the current domain,
        -- considering only domains as nodes
        linkingDepth TINYINT,
        
        -- this is the score we used to decide if the url is in English and about Tübingen or if it isn't (see more in the metric.py- file for that)
        tueEngScore DOUBLE)
    """)

# this table stores the current frontier if the program is stopped properly by entering the "stop"- command in the terminal
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS frontier (
        id BIGINT PRIMARY KEY,
        
        -- the schedule is the Unix- time at which the url was fetched + delay- Time determined for the website
        schedule DOUBLE,
        
        -- this is the delay that was assigned to the url by our crawler- algorithm, when the url was put into the frontier
        -- when the url is fetched, it can be that the overall delay will be bigger that that, since the maximum
        -- of the domain- delay and this delay is then taken to be the delay- Time 
        delay DOUBLE,
        
        -- this is just the url associated with this page in the frontier
        url TEXT UNIQUE,
        
        -- same meaning as in urlsDB
        incomingLinks TEXT,
        
        -- same meaning as in urlsDB
        domainLinkingDepth TINYINT,
        
        -- same meaning as in ulsDB
        linkingDepth TINYINT)
    """)


# here strings are stored, which were embedded in the xml/ html - file of an url the proper way for an url
# yet does not seem to be an url after all
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS strangeUrls (
        id BIGINT PRIMARY KEY,
        
        -- an url is stored in this table if the domain- determining process (helpers.getDomain) failed, we
        -- just store the url to be able to study when this does happen (we ended up not using this knowledge after all)
        url TEXT UNIQUE)
    """)

# stores the URLs for which we our algorithm detected (time- limited) banning of our crawler
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS disallowedUrls (
        id BIGINT PRIMARY KEY,
        url TEXT UNIQUE,
        
        -- reason here can be one of two: 
        -- -1. "counter" meaning: We did encounter a certain http- status- code 
        -- multiple times when we tried to fetch the url, and a threshold implemented in the handleCodes function was reached
        -- 2. "loop", meaning: Our algorithm determined that the url is part of a http- redirectton loop
         reason TEXT,
         
        -- the time the url was stored into disallowedUrls Cache, where the time has the format DD: MM: YYYY
        -- and it is regarding the local time- zone
        received TEXT)
    """)


# here we store the domains on which we detected (time- limited) banning of our crawler
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS disallowedDomains (
        id BIGINT PRIMARY KEY,
        domain TEXT UNIQUE,
        
        -- the time the domain was stored into the disallowedDomains Cache
        received TEXT,
        
        --  this is information about the time and kind of the last 100 http_status codes received for that domain
        -- it is stored as a list of tuples of the form (<status_code, time received), where the time has the format DD: MM: YYYY
        -- and it is regarding the local time- zone, it is json.dumps- encoded as a string
        data TEXT)
    """)

# this table is for storage only and not to be intended to be read out for anything else
# than loading the errorss into responseHttpErrorTracker
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS errorStorage (
        id BIGINT PRIMARY KEY,
        domain TEXT UNIQUE,
        
        -- the json.dumps- compressed content of responseHTTpErrorTracker[domain][data]
        data TEXT,
        
        -- the json.dumps-
        -- encoded content of responseHTTpErrorTracker[domain]["urlData"]
        urlData TEXT)
    """)

# this just stores the delay values per domain, such values can arise from robots.txt crawl- delays
# or from domain-wide crawl- speed throtteling as can happen in handleCodes
crawlerDB.execute("""
    CREATE TABLE IF NOT EXISTS domainDelays (
        id BIGINT PRIMARY KEY,
        domain TEXT UNIQUE,
        
        -- value that is the minimal crawl- delay for every url on that domain 
        delay DOUBLE)
    """)  

# this is just for the data- storage purpose, since it makes sense
# to have an integer id as the primary key of the SQL- lite tables
# and we do not want multiple rows getting the same id's

# Input: String, which specifies the table
# Output: the largest id- integre found in the table
def getLastStoredId(table):
    '''returns the biggest id from the gven table'''
    global crawlerDB
    result = crawlerDB.execute(f"SELECT MAX(id) FROM {table}").fetchone()
    last_id = result[0] if result[0] is not None else 0
      
    return last_id

  
# input: 
#       - structure: A dictionary
#       - columnNamesLst: The name of fields which we want to put into the output dictionary
#       - ignoreFields: Fields we don't want to look into or store in the (recursive) call(s) of makeRow
# oputput: a dictionary with fields with all the names contained in columnsLst
def makeRow(structure, fieldNamesLst, ignoreFields):
    '''given a dictionary, it searches the dictionary and its sub- dictionaries,
    until it has found fields of the names listed in columnLst, and returns a 
    dictionary cotaning only those fields, and while doing that
    it leaves fields untouched whose names are contained in ignoreFields'''
    dictOfRowValues = {}
    searchDictionaries = []
    copyInitialList = copy.deepcopy(fieldNamesLst)
    initialLengthOfFieldNamesLst = len(fieldNamesLst)
    
    
    if isinstance(structure, dict) and fieldNamesLst != None:
        for name in structure:
            if ignoreFields == None or name not in ignoreFields:
                    if name in fieldNamesLst:
                        del fieldNamesLst[fieldNamesLst.index(name)]
                        if isinstance(structure[name],(list, dict, heapdict)):
                            dictOfRowValues[name] =  "jsonDumps" + json.dumps(structure[name])
                        else:
                            dictOfRowValues[name] = structure[name]
                    else: 
                        if isinstance(structure[name], dict):
                            searchDictionaries.append(structure[name])
                            
        if fieldNamesLst != []:
            for dictionary in searchDictionaries:
                dictOfRowValues.update(makeRow(dictionary, fieldNamesLst, ignoreFields)) 
                            
    elif not fieldNamesLst:
        result = "jsonDumps" + json.dumps(structure) if isinstance(structure, (list, dict)) else structure
        return  result
    
    
    if isinstance(structure, (dict, heapdict, list)) and len(list(dictOfRowValues.keys())) < initialLengthOfFieldNamesLst:
        raise Error('''Somehow received a dictionary which did not contain all the fields (in sub- dictionaries) that were
                    given in fieldNamesLst''')     
    return dictOfRowValues
        
                        
# testDict = {"checkTest": {"fake": 16}, "test": {"hi there": {"fake": 7, "no way": "fail"} }}
# print(makeRow(testDict, ["fake"], ["checkTest"]) )    
# -> function works as intended, test successfull!       
  
  
#input: structure: The structure to be stored, 
#       -tableName: The name of the table into which we want to store the structure
#       -name: The name of the field in whose entries we want to search the names given in columnList
#       -columnNamesLst: the names of the fields that are associated to the columns in the resulting table (the output of the function), if it is empty, it means our dictionary is expected to have entries {name: value}, where value is not a dictionary
#        not including the name of the argument "field"
#       -disallowedFields we want to specifically not look into (speeds up makeRow)
#       -delete: If True, the table with name tableName is cleared, before the newly created row- entries are inserted
#       - nameOfColumn: A string, which names the column in the table, if the columnNamesLst is empty
def storeInTable(structure, tableName, name, columnNamesLst = None, disallowedFields =None,nameOfColumn="", delete = False):
    ''' stores all the dictionaries in structure[field]  into a table with name "tableName", where each row stores the data of one of the dictionaries 
    of field (There are some extra- options
    which determine which fields are stored, or if they should be string- encoded before, or if the cache (the structure) should
    be deleted afterwards, see the comment above the function"'''
    if columnNamesLst == None:
        columnNamesLst = []
    if disallowedFields == None:
        disalloweFields = []
    global crawlerDB
    
    id = getLastStoredId(tableName)+1
    if delete:  
        crawlerDB.execute(f"DELETE FROM {tableName} ")
    data = []
    initalColumnNamesLst = copy.deepcopy(columnNamesLst)
    for i,name_ in enumerate(structure):
        columnNamesLst_ = copy.deepcopy(columnNamesLst)
        temp = makeRow(structure[name_], columnNamesLst_, disallowedFields)
        
        if columnNamesLst == []:
            lst_ = [temp]
        else:
            lst_= [temp[a] for a in columnNamesLst]
            
        lst_.extend([name_, id+i])
        
        data.append(tuple(lst_))
        
    if columnNamesLst == []:   
        columnNamesLst.append(nameOfColumn)
    
    columnNamesLst += [name, "id"]
    columnNames = ",".join(columnNamesLst)
        
    if data != []:
        questionMarks = "(" + "?,"*(len(data[0])-1) + "?" + ")"
        crawlerDB.executemany(
            f"INSERT OR IGNORE INTO {tableName} ({columnNames}) VALUES {questionMarks}", data)
        crawlerDB.commit()
      

# input: 
#       - table: name of the table, which we want to read out
#       - field: name of the field 
#       - column, identifier: If we only want to read out a certain row, we give the identifier [col, value] and we only receive
#         the row- data stored for which the entry in col matches value
#          initially they are both "", and they are only used, if column != ""
#       - output: The dictionary that contains for each row of the table (or the one specified row) a dictionary of the table-    
#                 identifiers as the keys and the associated values as the field- values; returns None, if the column- argument 
#                 was used but no entry with matching column and identifier was found, or if the table was empty
#         , 
def readTable(table, field, columns = "", identifier =[]):
    ''' reads the the specified columns from table and 
        then stores them as a nested 1- level dictionary, such that
        structure has entries of form <field>: {column: <value| for column in columns}'''
    global crawlerDB
    cur = crawlerDB.execute(f"SELECT * FROM {table} LIMIT 0")
    resultDict = {}
    if columns =="":
         columns = [desc[0] for desc in cur.description]
         
    else:
        columns.append(field)
        
    
    fieldIndex = columns.index(field)
        
    columnsString = ",".join(columns)
    
    if len(identifier) ==2:
        rows = crawlerDB.execute(f"""SELECT {columnsString}  FROM {table} WHERE {identifier[0]} = ?""", (identifier[1],)).fetchall()
    else:
        rows = crawlerDB.execute(f"""SELECT {columnsString} FROM {table}""").fetchall()


    
    if rows != []:
        for r in rows:
            tempDict = {r[fieldIndex] : {columns[c]: (json.loads(r[c][9:]) if isinstance(r[c], str) and r[c][:9]=="jsonDumps"  else r[c]) for c in range(len(columns)) if columns[c] not in ["id", field]}}
            resultDict.update(tempDict)
    if "id" in resultDict:
        print("Why is the id in here")  
    return resultDict
        
        
def updateTableEntry(tableName, updates, identifier):
    ''' updates the value in the row of the table with name tableName where column identifier[0] matches with value identifier[1] '''
    global crawlerDB
    updatedValues = [updates[a] for a in updates]
    for index in range(len(updatedValues)):
        value = updatedValues[index]
        updatedValues[index] = "jsonDumps"+json.dumps(value) if isinstance(value, (list, dict)) else value
    updatedValues.append(identifier[1])
    updatedValues = tuple(updatedValues)
    columnNames = ",".join([a + "= ?" for a in updates])
    crawlerDB.execute(f'''UPDATE {tableName} SET {columnNames}
    WHERE {identifier[0]} = ?''',updatedValues)




    
def storeFrontier(frontier, frontierDict, domainDelaysFrontier): 
    ''' stores the frontier, the frontierDict, and the domainDelaysFrontier- Information
    in the table "frontier"'''
    for url in frontier:
        frontierDict[url]["schedule"] = frontier[url]
    storeInTable(frontierDict, 'frontier', 'url',columnNamesLst= ["domainLinkingDepth", "linkingDepth", "delay", "incomingLinks", "schedule"], delete= True )
    storeInTable(domainDelaysFrontier, 'domainDelays','domain',nameOfColumn="delay", delete = True)
    
    

def storeDisallowed(disallowedURLCache, disallowedDomainsCache):
    '''stores the disalloweURL- Cache in the table "disalloweUrls'''
    
    storeInTable(disallowedURLCache, "disallowedUrls", 'url', columnNamesLst=["reason","received"])
    storeInTable(disallowedDomainsCache, "disallowedDomains", 'domain', columnNamesLst = ["data", "received"])
    
    

        


def storeStrangeUrls(strangeUrls):
    '''stores the strangeUrls - Cache in the table strangeUrls '''
    storeInTable(strangeUrls,'strangeUrls','url')
 

def storeCache(cachedUrls, forced=False):
    '''stores chachedUrls into urlsDB, if len(cachedUrls)>1000, or forced, then empties cachedUrls'''
    if len(cachedUrls) > 1000 or forced:
        storeInTable(cachedUrls,"urlsDB", "url",columnNamesLst= ["incoming", "tueEngScore", "domainLinkingDepth", "linkingDepth", "text", "title",  "lastFetch"])
        cachedUrls.clear()
       

def cleanUpDisallowed(disallowedURLCache, disallowedDomainsCache):
    '''deletes all urls from disallowedURLCache, whos domains are already stored in disallowedDomainsCache'''
    for url in disallowedURLCache:
        if helpers.getDomain(url) in disallowedDomainsCache:
            del disallowedURLCache[url]
    
    
        
        
def  readUrlInfo(cachedUrls, url, delete=False):
    '''looks into the cache and the urlsDB- table in order to find an entry for a given url
    and returns it if found'''
    if url in cachedUrls:
        if isinstance(cachedUrls[url], str):
            print("how??")
        return cachedUrls[url]
    
    else:
        result = readTable("urlsDB", "url", identifier=["url", url])
        if result: 
            result = result[url]
            
        return result
    
    
# converts dictionaries with fields that contain dictionaries of the form {name: {sommeName: <data for someName}}
# into structures of the type of emptyStructure with fields of the form {name: <data for someName}
# we use it for structures of type heapDict and dict
def convertDict(emptyStructure, dict_):
    '''converts a dictonary with only one entry into another dictionary'''
    resultDict = emptyStructure
    if dict_:
        fieldName = next(iter(next(iter(dict_.values())).keys()))
        for name in dict_:
            resultDict[name] = dict_[name][fieldName]
    return resultDict

# loads the stored frontier-table values into the frontier, the frontierDict, as well as the domainDelays values into the domainDelaysFrontier
def loadFrontier():
    '''loads the stored frontier-table values into the frontier, the frontierDict, as well as the domainDelays values into the domainDelaysFrontier'''
    frontier = readTable("frontier", "url", columns= ["schedule"])
    frontier = convertDict(heapdict(), frontier)
    
    frontierDict = readTable("frontier", "url", columns = ["domainLinkingDepth", "linkingDepth", "delay", "incomingLinks"])
    domainDelaysFrontier = readTable("domainDelays", "domain")
    domainDelaysFrontier = convertDict({}, domainDelaysFrontier)
        
    
    return frontier, frontierDict, domainDelaysFrontier

def findDisallowedUrl(url, disallowedDomainsCache, disallowedURLCache):
    '''checks if the url is disallowed (in disallowedDomainsCache, or disallowedURLCache), and if yes, it returns True, else it returns false'''
    domain = helpers.getDomain(url)
    
    if not domain:
        return False
    disallowed = False

    if domain in disallowedDomainsCache:
        disallowed = True
    elif url in disallowedURLCache:
        disallowed = True
    return disallowed


def store(frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, disallowedDomainsCache, cachedUrls, 
          strangeUrls, responseHttpErrorTracker):
    '''stores all the caches into the corresponding tables (from memory to storage)'''
    storeFrontier(frontier, frontierDict, domainDelaysFrontier)
    cleanUpDisallowed(disallowedURLCache, disallowedDomainsCache)
    storeDisallowed(disallowedURLCache, disallowedDomainsCache)
    storeCache(cachedUrls, forced = True)
    
    
    # only this part has no extra- function and is therefore explained here:
    # this stores the data from the responseHttpErrorTracker into the table errorStorage
    storeInTable(responseHttpErrorTracker,'errorStorage', "domain",columnNamesLst= ["data", "urlData",], delete = True)
    
    # this part saves the last 10 stored entries of frontier and in case of urlsDB the last 100 stored 
    # urls together with some information into csv documents
    saveAsCsv("frontier", "id, schedule, delay, url",10)
    saveAsCsv("urlsDB", "url, lastFetch, tueEngScore",100)

# this is used int the main of the crawler to close the crawler    
def closeCrawlerDB():
    global crawlerDB
    crawlerDB.close()


def load():
    import frontierManagement
    global crawlerDB
    crawlerDB = duckdb.connect("crawlerDB.duckdb")
    '''loads all the tables entries into the caches (from storage to memory)'''
    frontier, frontierDict, domainDelaysFrontier = loadFrontier()
    
    # load the disallowed Domains and Urls
    disallowedURLCache = readTable("disallowedUrls", "url")
    
    disallowedDomainsCache = readTable("disallowedDomains", "domain")
    
    # load the error information from errorStorage int responseHttpErrorTracker
    responseHttpErrorTracker = readTable("errorStorage","domain")
    
    return (frontier, frontierDict, domainDelaysFrontier, disallowedURLCache, 
            disallowedDomainsCache, responseHttpErrorTracker)
    

def printNumberOfUrlsStored():
    global crawlerDB
    '''prints the size of the current urlsDB- table'''
    print(f'There are  {crawlerDB.execute("SELECT COUNT(*) FROM urlsDB").fetchone()} stored urls so far')   
    
    
# note that columns is a string of form "column1, column2, column3..."
# This function was written by chatGPT
def saveAsCsv(table, columns,limit):
    global crawlerDB
    '''safes the columns in columns in the specified table as a csv file'''
    table_exists = crawlerDB.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{table}'
    """).fetchone()[0]

    if not table_exists:
        print(f"Table '{table}' does not exist. Skipping export.")
        return

    result = crawlerDB.execute(f"SELECT COUNT(*) FROM {table} ").fetchone()[0]
    if result > 0:
        query = f"""
            COPY (
                SELECT {columns} FROM {table} ORDER BY id DESC LIMIT {limit}
            ) TO '{table}.csv' (HEADER, DELIMITER ',')
        """
        crawlerDB.execute(query)
        crawlerDB.commit()