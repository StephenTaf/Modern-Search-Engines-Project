import urllib.request
import json

url = "http://localhost:1984/generate_summary"
data = {
    "most_relevant_windows": ["Library in Tübingen is quiet and has a lot of books", "The old town of Tübingen is a beautiful place to visit", "The Neckar river is a nice place to walk along"],
    "query": "interesting places to visit in Tübingen",
}

req = urllib.request.Request(
    url,
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as response:
    result = json.loads(response.read().decode('utf-8'))
    print(result)
