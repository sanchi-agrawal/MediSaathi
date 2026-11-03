"""Literal-script evidence helpers, not OCR, translation or scheduling logic."""
import re
import unicodedata

DEVANAGARI=re.compile(r'[\u0900-\u097f\ua8e0-\ua8ff]')
TRANSLATE_DIGITS=str.maketrans('०१२३४५६७८९','0123456789')
MULTILINGUAL_GUIDE='''
Read English, Hindi in Devanagari, and mixed Hindi-English in the same image.
The interface language is irrelevant. Preserve original Unicode text exactly,
including Devanagari vowel marks, spelling, numerals, medicine brand names,
strengths, units, punctuation and abbreviations. Never translate or transliterate
names or raw fields into English. Never repair handwriting by guessing.
Preserve visible सुबह, दोपहर, शाम, रात, खाने से पहले, खाने के बाद and दिन तक
literally in the appropriate source fields. Do not map these to English slots or
infer clock times, meal timing, frequencies or quantities from abbreviations.
Recognize printed ASCII 0-9 and Devanagari ०-९ numerals without changing raw text.
Handwritten Hindi and ambiguous abbreviations are experimental: keep uncertain
values null, preserve readable source text and set needs_review true. Do not
invent missing medicines, ingredients, strengths or administration instructions.
'''

def has_devanagari(text):return bool(isinstance(text,str) and any(unicodedata.category(c)[0] in 'LMN' for c in DEVANAGARI.findall(text)))
def ascii_digits(text):return text.translate(TRANSLATE_DIGITS)

def script_observation(texts):
    text='\n'.join(t for t in texts if isinstance(t,str))
    deva=has_devanagari(text);latin=bool(re.search(r'[A-Za-z]',text))
    script='mixed' if deva and latin else 'devanagari' if deva else 'latin' if latin else 'unknown'
    # Script is evidence, not a language classifier: Marathi/Nepali also use it.
    return {'script':script,'source':'original_extracted_text','language_verified':False}

def explicit_days(text):
    text=ascii_digits(text)
    if re.search(r'\d\s*(?:[-–]|से|to)\s*\d\s*(?:दिन|days?)',text,re.I):return None
    found=[]
    for m in re.finditer(r'(?<![\w./-])([0-9]+)\s*(?:दिन(?:ों)?(?:\s*तक)?|days?)(?!\w)',text,re.I):
        before=text[max(0,m.start()-16):m.start()]
        after=text[m.end():m.end()+8]
        if re.search(r'(?:हर|प्रति|every|each)\s*$',before,re.I) or re.match(r'\s*में',after):return None
        found.append(int(m[1]))
    return found[0] if len(found)==1 and found[0]>0 else None

def hindi_flags(text,frequency=None,duration=None,quantity=None):
    if not has_devanagari(text):return set()
    flags=set()
    if re.search(r'(?:^|\s)(?:सु|दो|शा|रा|खा|दि)\s*\.',text):flags.add('frequency_requires_clarification')
    if re.search(r'(?:आवश्यकतानुसार|जरूरत\s*पर|ज़रूरत\s*पर|जरूरत\s*होने\s*पर)',text):flags.add('frequency_requires_clarification')
    if re.search(r'(?:फिर|घटाएँ|घटायें|कम\s*करें|बढ़ाएँ|बढाएं|एक\s*दिन\s*छोड़कर|बारी[- ]बारी)',text):flags.add('variable_or_tapering_instruction')
    if duration and re.search(r'\d\s*(?:[-–]|से|to)\s*\d',ascii_digits(duration),re.I):flags.add('duration_range')
    if quantity and re.search(r'\d\s*(?:[-–]|से|या)\s*\d',ascii_digits(quantity)):flags.add('variable_dose')
    return flags

def is_mass_unit(unit):
    return bool(unit and re.sub(r'[.\s]','',unit.casefold()) in
        {'mg','g','mcg','µg','μg','milligram','milligrams','मिग्रा','मिलीग्राम','ग्राम','माइक्रोग्राम'})

def guard_hindi_medicine(record):
    text=record.get('raw_text')
    if not has_devanagari(text):return
    record['needs_review']=True
    # A bilingual parenthesis can provide a literal Latin medicine identity.
    # This is a display normalization of visible text, never an ingredient lookup.
    latin=re.findall(r'\(([A-Za-z][A-Za-z .-]*?)\s+([0-9०-९]+)\s*(mg|g|mcg)\)',text,re.I)
    hindi_name=re.match(r'^\s*(.+?)\s+[0-9०-९]+\s*मि\.?\s*ग्रा\.?\s*\(',text)
    if len(latin)==1 and record.get('name') in (text,latin[0][0],hindi_name[1] if hindi_name else None):
        record['name']=latin[0][0].strip()
    normalized_strength_source=False
    strength=record.get('strength')
    if strength and strength in text:
        hindi=re.fullmatch(r'\s*([0-9०-९]+)\s*मि\.?\s*ग्रा\.?\s*',strength)
        if hindi:
            value=ascii_digits(hindi[1])+' mg'
            # Conflicting printed strengths must stay unresolved.
            if latin and (ascii_digits(latin[0][1])+' '+latin[0][2].lower())!=value:
                record['strength']=None
            else:record['strength']=value;normalized_strength_source=True
    for field in ('name','salt','strength','frequency_pattern','timing'):
        supported=(field=='name' and latin and record[field]==latin[0][0].strip()
                   or field=='strength' and record[field] and
                   (normalized_strength_source or latin and record[field]==ascii_digits(latin[0][1])+' '+latin[0][2].lower()))
        if record[field] is not None and record[field] not in text and not supported:record[field]=None
    if record['duration_days'] is not None and record['duration_days']!=explicit_days(text):record['duration_days']=None
    forms={'tablet':('tablet','tab','गोली','गोलियाँ','गोलियां','गोलियों'),'capsule':('capsule','कैप्सूल'),'syrup':('syrup','सिरप'),'drops':('drops','drop','बूंद','बूँद')}
    if record['form'] is None:
        found=[form for form,tokens in forms.items() if any(token in text.casefold() for token in tokens)]
        if len(found)==1:record['form']=found[0]
    if record['form'] is not None and not any(token in text.casefold() for token in forms[record['form']]):record['form']=None
    if hindi_flags(text):record['needs_review']=True

def numeric_previews(records,fields):
    output=[]
    for i,record in enumerate(records):
        for field in fields:
            value=record.get(field)
            if isinstance(value,str) and re.search('[०-९]',value):
                output.append({'record_index':i,'field':field,'original':value,'digit_reading':ascii_digits(value)})
    return output
