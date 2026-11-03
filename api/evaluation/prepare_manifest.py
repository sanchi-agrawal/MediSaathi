"""Write fictional ground truth only. Never requests an extraction/provider."""
import json
from pathlib import Path

BASE=Path(__file__).parent/'fixtures'

def examples():
    specs=[
        ('english_printed','printed','en','DEMO-C','5 mg','tablet',2,'once daily','morning after food',
         'DEMO-C 5 mg tablet','Take 1 tablet once daily in the morning after food for 2 days.',
         '1','tablet','2 days','Tests: DEMO-TEST','DEMO-TEST','Tests'),
        ('hindi_printed','printed','hi','डेमो-ए','१० मि.ग्रा.','tablet',5,'दिन में २ बार','सुबह और रात १ गोली, खाने के बाद',
         'डेमो-ए १० मि.ग्रा. गोली','सुबह और रात १ गोली, खाने के बाद, दिन में २ बार, ५ दिन तक लें।',
         '१','गोली','५ दिन तक','जाँच: नमूना-जाँच','नमूना-जाँच','जाँच'),
        ('mixed_printed','printed','hi-en','DEMO-B','20 mg','tablet',3,'दिन में 4 बार','सुबह, दोपहर, शाम और रात: 1 tablet, खाने से पहले',
         'DEMO-B 20 mg tablet','सुबह, दोपहर, शाम और रात: 1 tablet, खाने से पहले, दिन में 4 बार, ३ दिन तक।',
         '1','tablet','३ दिन तक','जाँच: DEMO-TEST','DEMO-TEST','जाँच'),
    ]
    output=[]
    for identifier,style,language,name,strength,form,days,frequency,timing,medicine,line,quantity,unit,duration,test,test_name,context in specs:
        raw=medicine+'\n'+line
        record=dict(raw_text=raw,name=name,salt=None,strength=strength,form=form,frequency_pattern=frequency,duration_days=days,timing=timing,confidence=None,needs_review=True)
        instructions={'instructions':[dict(medicine_name_raw=name,raw_text=raw,dose_quantity_raw=quantity,dose_unit_raw=unit,frequency_raw=frequency,route_raw=None,timing_raw=timing,duration_raw=duration,uncertainty_reasons=[],needs_review=True)],'issues':[]}
        investigations={'investigations':[dict(test_name_raw=test_name,raw_text=test,order_context_raw=context,specimen_raw=None,variant_raw=None,timing_raw=None,order_status='ordered',uncertainty_reasons=[],needs_review=True)],'issues':[]}
        output.append({'id':identifier,'file':identifier+'.png','style':style,'language':language,'synthetic':True,'patient_data':False,
          'lines':['केवल परीक्षण — वास्तविक पर्चा नहीं',medicine,line,test,'किसी व्यक्ति या उपचार के लिए नहीं।'],
          'expected_medicines':[record],'instruction_response':instructions,'investigation_response':investigations})
    alternate=json.loads(json.dumps(output[1],ensure_ascii=False));alternate.update(id='hindi_handwriting_like',file='hindi_handwriting_like.png',style='synthetic_handwriting_like',not_human_handwriting=True)
    alternate['lines'][0]='कृत्रिम लिखावट जैसा परीक्षण — मानव हस्तलेख नहीं'
    output.append(alternate)
    return output

if __name__=='__main__':
    BASE.mkdir(parents=True,exist_ok=True)
    (BASE/'manifest.json').write_text(json.dumps({'version':1,'fictional_only':True,'real_handwritten_samples':0,'fixtures':examples()},ensure_ascii=False,indent=2),encoding='utf8')
