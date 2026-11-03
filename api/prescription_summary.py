"""Localized labels over confirmed source values; no free medical translation."""
from .section_routes import section_view

COPY = {
    'en': {
        'title':'Your confirmed prescription summary', 'unknown':'Unknown / not recorded',
        'notice':'Only independently confirmed sections are included. Original names, text, numbers and units are preserved. This is not medical advice or scheduling approval.',
        'instructions':'Confirmed dosage instructions', 'investigations':'Confirmed investigations',
        'labels':['Medicine name as written','Original instruction','Dose quantity as written','Dose unit as written','Frequency as written','Route as written','Timing as written','Duration as written',
                  'Test name as written','Original test order','Order context','Specimen as written','Variant as written','Test timing as written'],
    },
    'hi': {
        'title':'आपके पुष्टि किए गए पर्चे का सारांश', 'unknown':'अज्ञात / दर्ज नहीं है',
        'notice':'केवल अलग से पुष्टि किए गए अनुभाग शामिल हैं। मूल नाम, पाठ, संख्याएँ और इकाइयाँ अपरिवर्तित हैं। यह चिकित्सा सलाह या समय-सारणी की अनुमति नहीं है।',
        'instructions':'पुष्टि किए गए खुराक निर्देश', 'investigations':'पुष्टि की गई जाँचें',
        'labels':['मूल दवा का नाम','मूल निर्देश','लिखी हुई खुराक की मात्रा','लिखी हुई खुराक की इकाई','लिखी हुई आवृत्ति','लिखा हुआ सेवन मार्ग','लिखा हुआ समय','लिखी हुई अवधि',
                  'मूल जाँच का नाम','मूल जाँच आदेश','आदेश का संदर्भ','लिखा हुआ नमूना','लिखा हुआ प्रकार','जाँच का लिखा हुआ समय'],
    },
    'hinglish': {
        'title':'Aapke confirmed prescription ka saar', 'unknown':'Maloom nahi / record mein nahi hai',
        'notice':'Sirf alag se confirmed sections shamil hain. Original naam, text, numbers aur units waise hi rakhe hain. Yeh medical advice ya schedule ki permission nahi hai.',
        'instructions':'Confirmed dosage instructions ka vivaran', 'investigations':'Confirmed jaanch ka vivaran',
        'labels':['Dawa ka original naam','Original instruction','Likhi hui dose quantity','Likhi hui dose unit','Likhi hui frequency','Likha hua route','Likha hua timing','Likhi hui duration',
                  'Jaanch ka original naam','Original test order','Order ka context','Likha hua specimen','Likha hua variant','Jaanch ka likha hua timing'],
    },
}
FIELDS = {
    'instructions':('medicine_name_raw','raw_text','dose_quantity_raw','dose_unit_raw','frequency_raw','route_raw','timing_raw','duration_raw'),
    'investigations':('test_name_raw','raw_text','order_context_raw','specimen_raw','variant_raw','timing_raw'),
}

def build_summary(session, language, enabled_sections):
    # Called under the session lock after the medicine API+AI confirmation gates.
    snap=session.ai.snapshot();root=snap['prescription'];copy=COPY[language]
    sections={}
    for scope,fields in FIELDS.items():
        labels=copy['labels'][:8] if scope=='instructions' else copy['labels'][8:]
        view=section_view(session,snap,scope) if scope in enabled_sections else None
        confirmed=bool(view and view['confirmed'])
        records=[]
        if confirmed:
            identity='instruction_id' if scope=='instructions' else 'investigation_id'
            for item in view['payload'][scope]:
                records.append({'record_id':item[identity], 'original_text':item['raw_text'],
                    'fields':[{'field':field,'label':label,'value':item[field], 'is_unknown':item[field] is None,
                               'text':label+': '+(item[field] if item[field] is not None else copy['unknown'])}
                              for field,label in zip(fields,labels)],
                    'uncertainty_reasons':list(item['uncertainty_reasons']), 'needs_review':item['needs_review']})
        sections[scope]={'title':copy[scope],'confirmed':confirmed,'records':records,
                         'issues':list(view['payload']['issues']) if confirmed else []}
    return {'schema_version':'confirmed-prescription-summary-v1','language':language,
            'title':copy['title'],'notice':copy['notice'],'medicine_count':len(root['sections']['medicines']['reviewed']),
            'sections':sections}
