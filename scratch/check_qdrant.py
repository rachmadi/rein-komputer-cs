import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:6333/collections/computer_products/points/scroll',
    data=b'{"limit": 100}',
    headers={'Content-Type': 'application/json'}
)
resp = json.loads(urllib.request.urlopen(req).read())
codes = [p['payload']['kode'] for p in resp['result']['points']]
print(codes)
print(f"Total: {len(codes)}")
