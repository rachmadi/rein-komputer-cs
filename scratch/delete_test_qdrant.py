import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:6333/collections/computer_products/points/delete',
    data=b'{"filter": {"must": [{"key": "kode", "match": {"value": "TEST-GPU-NULL"}}]}}',
    headers={'Content-Type': 'application/json'}
)
resp = json.loads(urllib.request.urlopen(req).read())
print(resp)
