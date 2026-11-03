"""Explain extraction flags; allow only explicit, source-supported review resolution."""
import re
from .dependencies import reader
from confirmed_frequency import canonical_pattern,pattern_occurs

VERIFY_FIELDS=('raw_text','name','salt','strength','form','frequency_pattern','duration_days','timing')

def requirements(original,records):
    result=[]
    for index,record in enumerate(records or []):
        source=original[index] if original and index<len(original) else None
        missing=[f for f in reader.FIELDS if f!='needs_review' and record.get(f) is None]
        confidence=source.get('confidence') if source else None
        confidence_state='unknown' if confidence is None else 'low' if confidence<.8 else 'acceptable'
        unsupported=[];text=record.get('raw_text') or ''
        if re.search(r'[?？]|_{2,}|\b(?:illegible|unreadable|blurred|uncertain|unclear)\b|अस्पष्ट',text,re.I):unsupported.append('raw_text')
        for field in ('name','salt','strength','frequency_pattern','timing'):
            value=record.get(field)
            supported=pattern_occurs(text,value) if field=='frequency_pattern' and canonical_pattern(value) else value in text if value else True
            if not supported:unsupported.append(field)
        form=record.get('form')
        forms={'tablet':r'\b(?:tablet|tablets|tab|tabs)\b','capsule':r'\b(?:capsule|capsules|cap|caps)\b','syrup':r'\b(?:syrup|mL|ml)\b','drops':r'\b(?:drops?|gtt)\b'}
        if form and (form not in forms or not re.search(forms[form],text,re.I)):unsupported.append('form')
        days=record.get('duration_days')
        if days and not re.search(r'(?<![\d-])'+str(days)+r'\s+days?\b',text,re.I):unsupported.append('duration_days')
        can_resolve=bool(source and source.get('raw_text') and not missing and not unsupported and confidence_state=='acceptable' and record.get('confidence')==confidence)
        result.append({'record_index':index,'flagged':record.get('needs_review') is True,
            'source_flagged':source.get('needs_review') is True if source else None,
            'missing_fields':missing,'unsupported_fields':unsupported,'confidence_state':confidence_state,
            'can_resolve':can_resolve,'required_verifications':list(VERIFY_FIELDS)})
    return result
