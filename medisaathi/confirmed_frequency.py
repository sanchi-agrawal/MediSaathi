"""Exact binary three-slot notation, never an OCR or dose inference engine."""
import re

def canonical_pattern(value):
    if not isinstance(value,str):return None
    space=r'[ \t\u00a0]*'
    match=re.fullmatch(space+r'([01])'+space+r'[-–]'+space+r'([01])'+space+r'[-–]'+space+r'([01])'+space,value)
    return '-'.join(match.groups()) if match and any(v=='1' for v in match.groups()) else None

def same_frequency(left,right):
    normalized=canonical_pattern(left)
    return normalized==canonical_pattern(right) if normalized else left==right

def remove_verified_pattern(text,pattern):
    normalized=canonical_pattern(pattern)
    if not normalized:return text
    token=r'[ \t\u00a0]*[-–][ \t\u00a0]*'.join(normalized.split('-'))
    return re.sub(r'(?<![\w\-–])'+token+r'(?![\w\-–])','',text)

def pattern_occurs(text,pattern):
    return isinstance(text,str) and remove_verified_pattern(text,pattern)!=text

def canonical_unit(value):
    return {'tab':'tablet','tabs':'tablet','tablet':'tablet','tablets':'tablet',
        'cap':'capsule','caps':'capsule','capsule':'capsule','capsules':'capsule',
        'ml':'mL','drop':'drop','drops':'drop'}.get(value.casefold()) if isinstance(value,str) else None

def three_slots(value):
    normalized=canonical_pattern(value)
    if normalized is None:return None
    values=[int(v) for v in normalized.split('-')]
    return dict(zip(('morning','noon','night','bedtime'),values+[0])) if any(values) else None

def explicit_days(value):
    match=re.fullmatch(r'(?:[x×]\s*)?([1-9]\d*) days?',value or '')
    return int(match.group(1)) if match else None

NAMED_SLOTS=('morning','afternoon','evening','night','bedtime')

def engine_slot_flags(slots):
    if type(slots) is not list or not slots or len(set(slots))!=len(slots) or any(s not in NAMED_SLOTS for s in slots):raise ValueError('Invalid confirmed named slots')
    keys=('morning','noon','evening','night','bedtime') if 'evening' in slots else ('morning','noon','night','bedtime')
    return {s:int(('afternoon' if s=='noon' else s) in slots) for s in keys}

def timing_proposal(medicine,item):
    """Review-layer evidence only. Calling this never confirms a proposal."""
    frequency=item.get('frequency_raw');timing=item.get('timing_raw') or ''
    if not frequency or not same_frequency(frequency,medicine.get('frequency_pattern')):return None
    numeric=three_slots(frequency)
    mentioned=[s for s in NAMED_SLOTS if re.search(r'\b'+('(?:noon|afternoon)' if s=='afternoon' else s)+r'\b',timing,re.I)]
    source=(item.get('raw_text') or '')+' '+(medicine.get('raw_text') or '')
    if numeric:
        if not pattern_occurs(item.get('raw_text'),frequency) or not pattern_occurs(medicine.get('raw_text'),medicine.get('frequency_pattern')):return None
        slots=[s for s in NAMED_SLOTS if numeric.get('noon' if s=='afternoon' else s,0)]
        if mentioned and mentioned!=slots:return None
        clean=remove_verified_pattern(source,frequency);kind='three_slot'
    else:
        expected={'BD':2,'BID':2,'TDS':3,'TID':3,'QID':4,'HS':1}
        if frequency not in expected or len(mentioned)!=expected[frequency] or not timing or timing not in (item.get('raw_text') or '') or frequency not in (item.get('raw_text') or ''):return None
        if frequency=='HS' and mentioned!=['bedtime']:return None
        slots=mentioned;clean=source;kind='literal'
    if re.search(r'\b(?:then|taper|reduce|alternate|increase|decrease|if|or|not|except|SOS|PRN)\b|\d\s*[-–]\s*\d',clean,re.I):return None
    return {'slots':slots,'kind':kind,'checked_source':clean}

def reviewed_semantic_timing(medicine,item):
    """Combined-review proposal: literal semantic timing takes precedence.

    This function proposes, never confirms, slots. Original text stays unchanged.
    """
    timing=item.get('timing_raw') or ''
    words={'morning':r'\bmorning\b|सुबह','afternoon':r'\b(?:noon|afternoon)\b|दोपहर','evening':r'\bevening\b|शाम','night':r'\bnight\b|रात','bedtime':r'\bbedtime\b|सोते समय'}
    named=[s for s in NAMED_SLOTS if re.search(words[s],timing,re.I)]
    if named and timing in (item.get('raw_text') or ''):
        numeric=three_slots(item.get('frequency_raw'))
        if numeric and engine_slot_flags(named)!=numeric:return None
        source=(item.get('raw_text') or '')+' '+(medicine.get('raw_text') or '')
        clean=remove_verified_pattern(source,item.get('frequency_raw'))
        if re.search(r'\b(?:then|taper|reduce|alternate|increase|decrease|if|or|not|except|SOS|PRN)\b|\d\s*[-–]\s*\d',clean,re.I):return None
        return {'slots':named,'kind':'semantic','checked_source':clean}
    return timing_proposal(medicine,item)
