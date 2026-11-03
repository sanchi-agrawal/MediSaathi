"""Small, source-reviewed information registry. Never a pricing/matching dataset.

Reviewed 2026-11-03. Only exact generic identities (with an optional printed
strength) or the documented Dolo 650 tablet tuple qualify. A brand name alone
or a fuzzy catalogue hit never qualifies. The route independently requires
current confirmed medicine review; original OCR review flags are not an
ingredient-identity check.
Facts are paraphrases, not a complete leaflet or patient-specific medical advice.
"""
import re
import unicodedata
VERSION='patient-drug-facts-2026-11-03-v2'
NPPA='https://nppa.gov.in/uploads/tender/e9aaeb95f8be19f55560c517991eec97.pdf'
BASE='https://www.nhs.uk/medicines/'
CORE_FIELDS=('what','uses','works','side_effects','precautions','urgent_signs')
FIELDS=('what','uses','benefits','works','side_effects','precautions','urgent_signs')
SOURCES={
 'paracetamol':[BASE+'paracetamol-for-adults/','https://www.medicines.org.uk/emc/product/5164/smpc',NPPA],
 'cetirizine':[BASE+'cetirizine/about-cetirizine/',BASE+'cetirizine/common-questions-about-cetirizine/',BASE+'cetirizine/side-effects-of-cetirizine/',BASE+'cetirizine/who-can-and-cannot-take-cetirizine/'],
 'omeprazole':[BASE+'omeprazole/','https://medlineplus.gov/druginfo/meds/a693050.html'],
}
FACTS={
 'paracetamol':{
  'en':[
   'Paracetamol is a medicine for pain and fever.',
   'It is commonly used for headaches, toothache and fever. This does not establish why your doctor prescribed it.',
   'It helps reduce pain and high temperature; its full mechanism is not completely understood.',
   'Most people have no side effects when using it correctly; serious reactions are rare.',
   'Check other medicines for paracetamol. Discuss liver or kidney problems and heavy alcohol use with a clinician.',
   'Seek urgent help for suspected overdose, even if you feel well. Breathing difficulty or throat swelling needs emergency care; yellow skin or eyes needs urgent assessment.'],
  'hi':[
   'Paracetamol दर्द और बुखार कम करने की दवा है।',
   'इसका उपयोग सिरदर्द, दाँत दर्द और बुखार में होता है। इससे यह तय नहीं होता कि डॉक्टर ने आपको यह क्यों दी है।',
   'यह दर्द और बढ़ा हुआ तापमान कम करने में मदद करती है; इसके काम करने का पूरा तरीका पूरी तरह स्पष्ट नहीं है।',
   'सही तरीके से लेने पर अधिकांश लोगों को दुष्प्रभाव नहीं होते; गंभीर प्रतिक्रियाएँ दुर्लभ हैं।',
   'दूसरी दवाओं में भी Paracetamol हो सकती है। जिगर या गुर्दे की समस्या और अधिक शराब सेवन के बारे में चिकित्सक से बात करें।',
   'अधिक मात्रा लेने का संदेह हो तो ठीक महसूस होने पर भी तुरंत चिकित्सा सहायता लें। साँस की परेशानी या गले की सूजन आपात स्थिति है; त्वचा या आँखें पीली हों तो तुरंत जाँच कराएँ।']},
 'cetirizine':{
  'en':[
   'Cetirizine is an antihistamine, a medicine for allergy symptoms.',
   'Common uses include sneezing, itchy eyes and hives. These uses do not tell us your personal diagnosis.',
   'It blocks histamine, a chemical involved in allergy symptoms.',
   'Sleepiness, tiredness, dry mouth, headache or nausea can occur.',
   'Avoid driving if sleepy. Tell a clinician about kidney problems, seizures, difficulty urinating and other medicines.',
   'Breathing difficulty or swelling of the mouth or throat needs emergency care. Unusual bruising or prolonged bleeding needs urgent medical advice.'],
  'hi':[
   'Cetirizine एलर्जी के लक्षण कम करने वाली एंटीहिस्टामिन दवा है।',
   'इसका उपयोग छींक, आँखों में खुजली और पित्ती में होता है। इन उपयोगों से आपकी व्यक्तिगत बीमारी का निष्कर्ष नहीं निकाला जा सकता।',
   'यह हिस्टामिन का असर रोकती है, जो एलर्जी के लक्षण पैदा करने में भूमिका निभाता है।',
   'नींद, थकान, मुँह सूखना, सिरदर्द या मितली हो सकती है।',
   'नींद आए तो गाड़ी न चलाएँ। गुर्दे की समस्या, दौरे, पेशाब में कठिनाई और दूसरी दवाओं के बारे में चिकित्सक को बताएँ।',
   'साँस लेने में कठिनाई या मुँह या गले की सूजन में तुरंत आपात सहायता लें। असामान्य नील पड़ने या देर तक खून बहने पर तुरंत चिकित्सा सलाह लें।']},
 'omeprazole':{
  'en':[
   'Omeprazole is a proton pump inhibitor, an acid-reducing medicine.',
   'It is used for reflux, heartburn and some stomach ulcers. Your doctor’s specific reason cannot be inferred here.',
   'It reduces the amount of acid made in the stomach.',
   'Headache, stomach pain, nausea, diarrhoea or constipation can occur.',
   'Discuss other medicines, liver or kidney problems and osteoporosis with a clinician. Do not change treatment based on this information.',
   'Breathing difficulty or throat swelling needs emergency care. New rash with joint pain or other serious symptoms needs prompt medical assessment.'],
  'hi':[
   'Omeprazole पेट का अम्ल कम करने वाली प्रोटॉन पंप इन्हिबिटर दवा है।',
   'यह अम्ल वापस आने, सीने में जलन और कुछ पेट के अल्सर में उपयोग होती है। डॉक्टर ने आपको यह क्यों दी है, इसका अनुमान यहाँ नहीं लगाया जा सकता।',
   'यह पेट में बनने वाले अम्ल की मात्रा कम करती है।',
   'सिरदर्द, पेट दर्द, मितली, दस्त या कब्ज हो सकते हैं।',
   'दूसरी दवाओं, जिगर या गुर्दे की समस्या और कमजोर हड्डियों के बारे में चिकित्सक से बात करें। इस जानकारी से उपचार न बदलें।',
   'साँस की परेशानी या गले की सूजन में तुरंत आपात सहायता लें। नया चकत्ता और जोड़ों का दर्द या अन्य गंभीर लक्षण हों तो जल्दी चिकित्सा जाँच कराएँ।']},
}

BENEFITS={
 'paracetamol':{
  'en':'It can ease pain and lower a high temperature. This does not tell us the cause of your symptoms.',
  'hi':'यह दर्द कम करने और बुखार में तापमान घटाने में मदद कर सकती है। इससे आपके लक्षणों का कारण पता नहीं चलता।'},
 'cetirizine':{
  'en':'It can ease allergy symptoms such as sneezing, itching and hives. This does not establish your diagnosis.',
  'hi':'यह छींक, खुजली और पित्ती जैसे एलर्जी के लक्षण कम कर सकती है। इससे आपकी बीमारी की पुष्टि नहीं होती।'},
 'omeprazole':{
  'en':'By reducing stomach acid, it can ease heartburn and reflux and help some ulcers heal. This does not establish why it was prescribed to you.',
  'hi':'पेट का अम्ल कम करके यह सीने की जलन और अम्ल वापस आने की तकलीफ़ घटा सकती है और कुछ अल्सर के भरने में मदद कर सकती है। इससे यह तय नहीं होता कि यह आपको क्यों दी गई है।'},
}

def approved_facts(ingredient,language):
    facts=dict(zip(CORE_FIELDS,FACTS[ingredient][language]))
    facts['benefits']=BENEFITS[ingredient][language]
    return {field:facts[field] for field in FIELDS}

def identify(record):
    def norm(value):return ' '.join(unicodedata.normalize('NFKC',value or '').casefold().split())
    name=norm(record.get('name'));salt=norm(record.get('salt'));strength=norm(record.get('strength'))
    form=record.get('form')
    for generic in FACTS:
        match=re.fullmatch(re.escape(generic)+r'(?:\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g)))?',name)
        if not match:continue
        printed_strength=norm(match.group(1)) if match.group(1) else None
        if salt and salt!=generic: return None
        if printed_strength and strength and printed_strength.replace(' ','')!=strength.replace(' ',''):return None
        if form not in (None,'tablet','capsule','syrup','drops'):return None
        return generic
    if name in ('dolo','dolo 650','dolo-650') and salt in ('','paracetamol') and re.fullmatch(r'650\s*mg',strength) and form=='tablet':return 'paracetamol'
    return None
