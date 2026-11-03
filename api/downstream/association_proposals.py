"""Read-only exact-name proposals. Only an explicit association POST approves a pair."""
import re
def key(value):
    return ' '.join(value.split()).casefold() if isinstance(value,str) else ''


def proposals(medicines,instructions,associations):
    result=[]
    for index,medicine in enumerate(medicines,1):
        ref=f'medicine_{index:03}';name=key(medicine.get('name'))
        saved=next((a for a in associations if a['medicine_ref']==ref),None)
        matches=[i for i in instructions if name and key(i.get('medicine_name_raw'))==name]
        unique_medicine=sum(key(m.get('name'))==name for m in medicines)==1
        available=[i for i in matches if not any(a['instruction_id']==i['instruction_id'] and a['medicine_ref']!=ref for a in associations)]
        if saved:status='confirmed';instruction_id=saved['instruction_id']
        elif not instructions:status='missing_instruction';instruction_id=None
        elif len(matches)==1 and len(available)==1 and unique_medicine and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',key(available[0].get('raw_text'))):
            status='proposed';instruction_id=available[0]['instruction_id']
        elif matches:status='ambiguous';instruction_id=None
        else:status='unmatched';instruction_id=None
        result.append({'medicine_ref':ref,'instruction_id':instruction_id,'status':status})
    return result
