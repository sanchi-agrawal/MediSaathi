"""Fetch only the public, pinned BodyParts3D blobs in brain-sources.json.
Run from frontend. Geometry is CC BY-SA 2.1 Japan; see the shipped attribution.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'public/models/brain-sources.json').read_text())
destination = root / '.anatomy-work'
destination.mkdir(exist_ok=True)

def fetch(source):
    target = destination / (source['id'] + '.stl')
    if target.exists():
        data = target.read_bytes()
        if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == source['gitBlob']:
            return source['id']
    request = urllib.request.Request(source['blobUrl'], headers={'User-Agent': 'MediSaathi-asset-build'})
    with urllib.request.urlopen(request, timeout=40) as response:
        data = base64.b64decode(json.load(response)['content'])
    assert len(data) == source['bytes'], source['id']
    assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == source['gitBlob']
    target.write_bytes(data)
    return source['id']

with ThreadPoolExecutor(max_workers=4) as pool:
    for index, name in enumerate(pool.map(fetch, manifest['components'] + manifest['alignmentReferences']), 1):
        print(f'{index}: verified {name}', flush=True)
