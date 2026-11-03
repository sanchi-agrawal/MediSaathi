"""Offline metrics for supplied fictional predictions. NEVER calls an OCR API."""
import argparse
import json
from pathlib import Path
from .prepare_manifest import BASE

FIELDS=('raw_text','name','salt','strength','form','frequency_pattern','duration_days','timing')
GROUPS=('printed','handwritten','synthetic_handwriting_like')

def distance(a,b):
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=row
    return previous[-1]

def evaluate(manifest,predictions=None):
    predictions=predictions or {'mode':'none','predictions':{}}
    declared=predictions.get('mode','unknown')
    supplied=predictions.get('predictions',{})
    groups={g:{'available_images':0,'evaluated_images':0,'provider_failures':0,'expected_nonnull_fields':0,'matched_fields':0,'unsupported_nonnull_fields':0,'extra_records':0,'extra_fields':0,'raw_characters':0,'character_errors':0} for g in GROUPS}
    for fixture in manifest['fixtures']:
        group=groups[fixture['style']];group['available_images']+=1
        result=supplied.get(fixture['id'])
        if result is None:continue
        if result.get('error'):
            group['provider_failures']+=1;continue
        rows=result.get('medicines')
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('Invalid fictional prediction records')
        expected=fixture['expected_medicines'];group['evaluated_images']+=1
        group['extra_records']+=max(0,len(rows)-len(expected))
        for r in rows:group['extra_fields']+=len(set(r)-set(FIELDS)-{'confidence','needs_review'})
        for i,wanted in enumerate(expected):
            actual=rows[i] if i<len(rows) else {}
            for field in FIELDS:
                value=wanted[field]
                if value is None:
                    group['unsupported_nonnull_fields']+=actual.get(field) is not None
                else:
                    group['expected_nonnull_fields']+=1
                    group['matched_fields']+=type(value) is type(actual.get(field)) and value==actual.get(field)
            raw=wanted['raw_text'] or '';read=actual.get('raw_text') or ''
            if not isinstance(read,str) or len(read)>10000:raise ValueError('Invalid fictional source text')
            group['raw_characters']+=len(raw);group['character_errors']+=distance(raw,read)
    for g in groups.values():
        g['field_exact_match_rate']=g['matched_fields']/g['expected_nonnull_fields'] if g['expected_nonnull_fields'] else None
        g['character_error_rate']=g['character_errors']/g['raw_characters'] if g['raw_characters'] else None
        g['status']='not_evaluated' if not g['evaluated_images'] else 'supplied_prediction_metrics_only'
    return {'declared_prediction_mode':declared,'provider_provenance':'not_verified_by_this_offline_tool',
            'real_ocr_accuracy_verified':False,'simulation_is_not_ocr':declared!='real_gemini',
            'handwriting_like_is_not_human_handwriting':True,'groups':groups}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',type=Path)
    args=parser.parse_args()
    manifest=json.loads((BASE/'manifest.json').read_text(encoding='utf-8-sig'))
    supplied=json.loads(args.predictions.read_text(encoding='utf8')) if args.predictions else None
    print(json.dumps(evaluate(manifest,supplied),indent=2))

if __name__=='__main__':main()
