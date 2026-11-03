"""Exact-hash static fixture dispatch; never presents itself as real OCR."""
import copy
import hashlib
import json
from pathlib import Path
from .dependencies import reader
import medication_instructions
import investigations

MANIFEST=Path(__file__).parent/'evaluation'/'fixtures'/'manifest.json'
def lookup(data):
    if not MANIFEST.exists():return None
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
    digest=hashlib.sha256(data).hexdigest()
    return next((copy.deepcopy(f) for f in manifest['fixtures'] if f.get('sha256')==digest),None)

def extract(data,scope):
    fixture=lookup(data)
    if fixture is None:raise reader.ImageInputError('Use a registered fictional fixture in offline mode.')
    digest=hashlib.sha256(data).hexdigest()
    if scope=='medicines':return reader.normalize_model_response(fixture['expected_medicines'])
    if scope=='instructions':return medication_instructions.normalize_medication_instructions_response(fixture['instruction_response'],source_image_sha256=digest)
    if scope=='investigations':return investigations.normalize_investigations_response(fixture['investigation_response'],source_image_sha256=digest)
    raise ValueError('Unsupported fictional scope')
