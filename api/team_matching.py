"""Fuzzy catalogue identification is never clinical approval or enrichment."""
import csv,re
from pathlib import Path
from .vendor.person2.matcher import match_medicine
CATALOGUE=Path(__file__).parent/'vendor/person2/data/medicines.csv'
def catalogue():
    with CATALOGUE.open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))
def norm(v):return ' '.join(str(v or '').casefold().split())
def release(v):
    aliases={'sustained release':'sr','controlled release':'cr','extended release':'er','immediate release':'ir','delayed release':'dr','modified release':'mr','enteric coated':'ec','xr':'er','xl':'er'}
    return {aliases.get(v,v) for v in re.findall(r'\b(?:sr|cr|er|xr|ir|mr|dr|xl|ec|extended release|sustained release|immediate release|controlled release|delayed release|modified release|enteric coated)\b',norm(v))}
def identify(medicine,rows=None):
    rows=catalogue() if rows is None else rows
    source_release=release(str(medicine.get('name') or '')+' '+str(medicine.get('raw_text') or ''))
    compatible=[]
    for row in rows:
        if any(medicine.get(k) and row.get(k) and norm(medicine[k])!=norm(row[k]) for k in ('salt','strength','form')):continue
        candidate_release=release(row.get('release_type') or row.get('name'))
        if source_release and candidate_release and source_release!=candidate_release:continue
        compatible.append(row)
    result=match_medicine(medicine,compatible)
    candidates=[]
    for item in result['candidates']:
        # A low similarity score is not a usable identity candidate.
        if item['score']<60:continue
        missing=[k for k in ('salt','strength','form') if not medicine.get(k) or not item.get(k)]
        raw=next(row for row in compatible if row['catalog_id']==item['catalog_id'])
        if not source_release or not release(raw.get('release_type') or raw.get('name')):missing.append('release_type')
        candidates.append({**item,'candidate_id':'person2:catalogue:'+str(item['catalog_id']),
                           'review_reasons':missing,'identity_verified':False})
    return {'state':'review_required' if candidates else 'unmatched','candidates':candidates,'selected':None,
            'message':'Candidate identification only. Example catalogue metadata is unverified; no substitution or cheaper-alternative recommendation.'}
