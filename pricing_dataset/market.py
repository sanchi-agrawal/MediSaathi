"""Provisional workbook listings alongside, never inside, the verified quote gate.

Reuses Person 2's normalization and platform URL registry. The old audit/lookup
contract remains authoritative for verified comparisons. No network requests.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from zipfile import ZipFile
from .lookup import _name
from .workflow import DOMAINS

DATA = Path(__file__).with_name('market_listings.json')
PLATFORMS = {'tata 1mg':'tata_1mg','apollo 24/7':'apollo_247','apollo pharmacy':'apollo_247','pharmeasy':'pharmeasy'}
LABELS = {'tata_1mg':'Tata 1mg','apollo_247':'Apollo 24/7 / Apollo Pharmacy','pharmeasy':'PharmEasy'}
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def sheets(path):
    """Read values without executing formulas or modifying the supplied workbook."""
    with ZipFile(path) as archive:
        shared = [''.join(v.itertext()) for v in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',NS)] if 'xl/sharedStrings.xml' in archive.namelist() else []
        rels = {r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            filename=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=[]
            for row in ET.fromstring(archive.read(filename)).findall('s:sheetData/s:row',NS):
                values={}
                for cell in row:
                    if cell.find('s:f',NS) is not None:raise ValueError('Formula cells require source review')
                    column=0
                    for char in re.match(r'[A-Z]+',cell.attrib['r'])[0]:column=column*26+ord(char)-64
                    v=cell.find('s:v',NS)
                    text=v.text if v is not None else ''.join(cell.find('s:is',NS).itertext()) if cell.find('s:is',NS) is not None else ''
                    values[column-1]=shared[int(text)] if cell.get('t')=='s' else text or ''
                if values:rows.append([values.get(i,'') for i in range(max(values)+1)])
            headers=rows[0]
            if len(set(headers))!=len(headers):raise ValueError('Duplicate headers')
            result[sheet.attrib['name']]=[dict(zip(headers,row+['']*(len(headers)-len(row)))) for row in rows[1:] if any(row)]
        return result

def medicine(row):
    required={'med_id','brand_name','salt','strength','dosage_form','manufacturer'}
    if not required<=row.keys() or not all(isinstance(v,str) for v in row.values()) or not row['med_id'].strip() or not row['brand_name'].strip():raise ValueError('Invalid catalogue row')
    return dict(item_id=row['med_id'],name=row['brand_name'],composition=row['salt'] or None,strength=row['strength'] or None,form=row['dosage_form'] or None,manufacturer=row['manufacturer'] or None,pack_size=None,raw=row)

def observation(row,ids):
    required={'obs_id','med_id','platform','listed_name','mrp_inr','selling_price_inr','availability','city','url','category'}
    if not required<=row.keys() or not all(isinstance(v,str) for v in row.values()) or not row['obs_id'].strip() or row['med_id'] not in ids or not row['listed_name'].strip():raise ValueError('Invalid observation reference')
    platform=PLATFORMS.get(_name(row['platform']))
    city={'delhi':'Delhi','gurgaon':'Gurgaon'}.get(_name(row['city']))
    if platform is None or city is None or row['availability'] not in ('in_stock','out_of_stock'):raise ValueError('Unsupported platform, city or availability')
    url=urlsplit(row['url']);domains=DOMAINS[platform] | ({'www.apollopharmacy.in','apollopharmacy.in'} if platform=='apollo_247' else set())
    if url.scheme!='https' or url.hostname not in domains or url.username or url.password or url.port not in (None,443):raise ValueError('Invalid source URL')
    normalized=[]
    def amount(value):
        if not value:return None
        try:
            number=Decimal(value)
            if not number.is_finite() or number<0:raise ValueError('Invalid price')
            rounded=number.quantize(Decimal('.01'))
            if abs(number-rounded)>Decimal('0.000000001'):raise ValueError('Invalid sub-paise price')
            if number!=rounded:normalized.append('excel_numeric_precision_normalized')
            return format(rounded,'.2f')
        except InvalidOperation:raise ValueError('Invalid price') from None
    mrp,selling=amount(row['mrp_inr']),amount(row['selling_price_inr'])
    warnings=['collection_date_missing','pack_quantity_unknown','source_not_independently_verified','delivery_pincode_unknown']
    warnings+=sorted(set(normalized))
    if mrp is not None and selling is not None and Decimal(selling)>Decimal(mrp):warnings.append('selling_exceeds_mrp')
    return dict(observation_id=row['obs_id'],item_id=row['med_id'],platform=platform,platform_name=LABELS[platform],listed_name=row['listed_name'],mrp_inr=mrp,selling_price_inr=selling,availability=row['availability'],city=city,url=row['url'],category=row['category'] or None,verification_status='provisional',historical=True,observed_at=None,pack_size=None,warnings=warnings,raw=row)

def build(path):
    source=sheets(path);items=[];observations=[];rejected=[];ids=set();seen=set()
    for row in source['Medicine Catalogue']:
        try:
            item=medicine(row)
            if item['item_id'] in ids:raise ValueError('Duplicate medicine ID')
            ids.add(item['item_id']);items.append(item)
        except ValueError as error:rejected.append({'kind':'medicine','raw':row,'reason':str(error)})
    for row in source['Price Observations']:
        try:
            item=observation(row,ids)
            signature=(item['item_id'],item['platform'],item['city'],item['url'])
            if item['observation_id'] in seen or signature in seen:raise ValueError('Duplicate observation')
            seen.update((item['observation_id'],signature));observations.append(item)
        except ValueError as error:rejected.append({'kind':'observation','raw':row,'reason':str(error)})
    return dict(schema_version='market-listed-v1',source_filename=Path(path).name,source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),items=items,observations=observations,rejected=rejected)

def load(path=DATA):
    data=json.loads(Path(path).read_text(encoding='utf8'))
    if data['schema_version']!='market-listed-v1':raise ValueError('Unknown listing schema')
    items=[medicine(v['raw']) for v in data['items']];ids={v['item_id'] for v in items}
    observations=[observation(v['raw'],ids) for v in data['observations']]
    if items!=data['items'] or observations!=data['observations'] or len(ids)!=len(items) or len({v['observation_id'] for v in observations})!=len(observations) or len({(v['item_id'],v['platform'],v['city'],v['url']) for v in observations})!=len(observations):raise ValueError('Invalid or duplicate listing data')
    return data

def search(data,query=''):
    tokens=re.findall(r'\w+',_name(query))
    return [v for v in data['items'] if all(any(word.startswith(token) for word in re.findall(r'\w+',_name(' '.join(str(v[k] or '') for k in ('name','composition','strength','form'))))) for token in tokens)]

def summary(data):
    return dict(medicines=len(data['items']),observations=len(data['observations']),rejected=len(data['rejected']),provisional=len(data['observations']),ambiguous=sum('selling_exceeds_mrp' in v['warnings'] for v in data['observations']),platforms=dict(Counter(v['platform_name'] for v in data['observations'])),cities=dict(Counter(v['city'] for v in data['observations'])),availability=dict(Counter(v['availability'] for v in data['observations'])))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--import-workbook',type=Path);args=parser.parse_args()
    if args.import_workbook:
        data=build(args.import_workbook);encoded=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
        if DATA.exists() and json.loads(DATA.read_text(encoding='utf8'))['source_sha256']!=data['source_sha256']:raise SystemExit('Different workbook already exists; explicit reconciliation required')
        DATA.write_text(encoded,encoding='utf8')
    print(json.dumps(summary(load()),ensure_ascii=False,indent=2))
