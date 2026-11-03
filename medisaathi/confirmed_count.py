"""Literal daily-count evidence, bound during explicit instruction association.

Never interprets numeric slot notation or abbreviations as a count. This is used
in the review/association layer, not by schedule generation.
"""
import re
from prescription_language import ascii_digits

def literal_count(medicine,item):
    text=item.get('raw_text') or '';frequency=item.get('frequency_raw') or ''
    # Called only when independently confirmed records are genuinely associated.
    # The current instruction is the prescribing source; a legacy medicine OCR
    # frequency is not a second authoritative frequency and must not override it.
    if not medicine.get('name') or not frequency or frequency not in text:return None
    if re.search(r'\b(?:then|taper|alternate|reduce|increase|decrease|if|or|not|except|PRN|SOS)\b|\d\s*[-–]\s*\d',text,re.I):return None
    patterns={1:r'once\s+(?:a\s+day|per\s+day|daily)|एक\s*बार\s*(?:रोज़|रोज|प्रतिदिन)',
              2:r'twice\s+(?:a\s+day|per\s+day|daily)|दो\s*बार\s*(?:रोज़|रोज|प्रतिदिन)',
              3:r'three\s+times\s+(?:a\s+day|per\s+day|daily)|तीन\s*बार\s*(?:रोज़|रोज|प्रतिदिन)',
              4:r'four\s+times\s+(?:a\s+day|per\s+day|daily)',5:r'five\s+times\s+(?:a\s+day|per\s+day|daily)'}
    counts={n for n,pattern in patterns.items() if re.fullmatch(pattern,frequency,re.I)}
    hindi=re.fullmatch(r'दिन\s+में\s+(एक|दो|तीन|चार|पाँच|[1-5])\s+बार',ascii_digits(frequency))
    if hindi:counts.add({'एक':1,'दो':2,'तीन':3,'चार':4,'पाँच':5}.get(hindi[1],int(hindi[1]) if hindi[1].isascii() else 0))
    m=re.fullmatch(r'([1-5])\s+times\s+(?:a\s+day|per\s+day|daily)',frequency,re.I)
    if m:counts.add(int(m[1]))
    if re.fullmatch(r'once\s+(?:at\s+(?:night|bedtime)|in\s+the\s+(?:morning|afternoon|evening))',frequency,re.I):counts.add(1)
    if len(counts)!=1:return None
    count=next(iter(counts))
    timing=item.get('timing_raw') or ''
    words={'morning':r'\bmorning\b|सुबह','afternoon':r'\b(?:afternoon|noon)\b|दोपहर','evening':r'\bevening\b|शाम','night':r'\bnight\b|रात','bedtime':r'\bbedtime\b|सोते समय'}
    slots=[slot for slot,pattern in words.items() if re.search(pattern,frequency+' '+timing,re.I)]
    if slots and (len(slots)!=count or timing and timing not in text):return None
    return {'count':count,'checked_source':text,'slots':slots}
