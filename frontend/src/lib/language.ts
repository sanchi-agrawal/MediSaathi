import { useSyncExternalStore } from 'react'
import { workflowHindi } from './workflowHindi'
import { settingsHindi } from './settingsHindi'
import { recognitionHindi } from './recognitionHindi'
import { scheduleHindi } from './scheduleHindi'
import { restoredFeaturesHindi } from './restoredFeaturesHindi'
import { reviewRequirementsHindi } from './reviewRequirementsHindi'
import { namedSlotsHindi } from './namedSlotsHindi'
import { confirmedWorkflowHindi } from './confirmedWorkflowHindi'
import { clockSchedulingHindi } from './clockSchedulingHindi'
import { patientExplanationHindi } from './patientExplanationHindi'
import { marketPricingHindi } from './marketPricingHindi'
import { manualPlannerHindi } from './manualPlannerHindi'
import { documentHindi } from './documentHindi'
export type Language = 'en' | 'hi'
const key = 'medisaathi.interface-language'
let current: Language = (() => { try { return localStorage.getItem(key) === 'hi' ? 'hi' : 'en' } catch { return 'en' } })()
const listeners = new Set<() => void>()
if (typeof document !== 'undefined') document.documentElement.lang = current
if (typeof window !== 'undefined') window.addEventListener('storage', event => {
  if (event.key === key) {
    current = event.newValue === 'hi' ? 'hi' : 'en'
    document.documentElement.lang = current
    listeners.forEach(listener => listener())
  }
})
export function setLanguage(language: Language) {
  current = language
  try { localStorage.setItem(key, language) } catch { /* Storage may be disabled. */ }
  document.documentElement.lang = language
  listeners.forEach(listener => listener())
}
export function useLanguage() {
  const language = useSyncExternalStore(callback => { listeners.add(callback); return () => { listeners.delete(callback) } }, () => current)
  return { language, setLanguage, t: translate }
}
export const hindi: Record<string, string> = {
  'Anatomy controls':'शरीर रचना के नियंत्रण',
  'Move your pointer to rotate. Drag to explore.':'घुमाने के लिए पॉइंटर चलाएँ। अधिक देखने के लिए खींचें।',
  'Brain unavailable. Other organs remain available.':'मस्तिष्क उपलब्ध नहीं है। अन्य अंगों की जानकारी उपलब्ध है।',
  'Body outline unavailable. Showing original organs.':'शरीर की बाहरी आकृति उपलब्ध नहीं है। मूल अंग दिखाए जा रहे हैं।',
  '3D unavailable. Please reload to try again.':'3D उपलब्ध नहीं है। फिर से कोशिश करने के लिए पेज दोबारा लोड करें।',
  'Anatomical organ model':'आंतरिक अंगों का शारीरिक मॉडल',
  'Hindi hero first':'अपनी दवाइयों को बेहतर समझें।','Hindi hero second':'अपनी सेहत का ध्यान रखें।',
  'Toggle navigation':'नेविगेशन खोलें या बंद करें','Main navigation':'मुख्य नेविगेशन','The experience':'हमारी सुविधाएँ','How it works':'यह कैसे काम करता है','Explore dashboard':'डैशबोर्ड देखें','Sign in':'साइन इन करें','Get started':'शुरू करें',
  'A LITTLE CLARITY. A LITTLE MORE CARE.':'थोड़ी स्पष्टता। थोड़ा और ध्यान।',
  'Your health deserves to make sense. Meet a calmer way to review prescriptions, understand instructions, and keep your next steps in view.':'MediSaathi आपके प्रिस्क्रिप्शन, दवाइयों के निर्देश और ज़रूरी जाँचों को आसान भाषा में समझने में मदद करता है।',
  'Start with your prescription':'अपना प्रिस्क्रिप्शन अपलोड करें','Review before you confirm':'पुष्टि करने से पहले जाँचें','Built with India in mind':'भारत की ज़रूरतों को ध्यान में रखकर',
  'A BETTER CONNECTION TO YOUR HEALTH':'अपनी सेहत को बेहतर समझें','INTERACTIVE':'इंटरैक्टिव','A clearer picture.':'ज़्यादा स्पष्ट जानकारी।','A more informed you.':'बेहतर समझ, आपके लिए।',
  'Our approach':'हमारा दृष्टिकोण','THOUGHTFULLY BUILT':'सोच-समझकर बनाया गया','Around your everyday care.':'आपकी रोज़मर्रा की देखभाल के लिए।','Your prescription,':'आपका प्रिस्क्रिप्शन,','in focus':'स्पष्ट रूप में','Your review,':'आपकी जाँच,','always first':'सबसे पहले','Your next steps,':'आपके अगले कदम,','together':'एक साथ',
  'LESS OVERWHELM. MORE UNDERSTANDING.':'कम उलझन। बेहतर समझ।','Care starts with clarity.':'स्पष्ट जानकारी से देखभाल की शुरुआत।','From the first scan to the details that matter.':'पहले स्कैन से लेकर हर ज़रूरी जानकारी तक।','One considered space for your healthcare.':'आपकी स्वास्थ्य देखभाल के लिए एक जगह।',
  'Prescription analysis':'प्रिस्क्रिप्शन विश्लेषण','A clearer view of what is written. Review extracted medicine details alongside your original image.':'लिखी हुई जानकारी को बेहतर समझें। निकाले गए दवाइयों के विवरण को मूल तस्वीर से मिलाकर जाँचें।','START WITH A SCAN':'स्कैन से शुरुआत करें',
  'Medication instructions':'दवा लेने के निर्देश','Keep explicit dosage, timing and duration together, with uncertain details marked for your review.':'स्पष्ट रूप से लिखी खुराक, समय और अवधि एक साथ देखें। अनिश्चित जानकारी आपकी जाँच के लिए चिह्नित रहती है।','CLARITY IN EVERY DETAIL':'हर जानकारी में स्पष्टता',
  'Investigations':'जाँचें','SEE THE FULL PICTURE':'पूरी जानकारी देखें',
  'Medicine expiry scanner':'दवा की एक्सपायरी स्कैनर','CHECK THE SMALL PRINT':'बारीक लिखी जानकारी जाँचें',
  'Medicine management':'दवाइयों का प्रबंधन','A home for reviewed medicines and your care routine. Schedule integration is coming next.':'जाँची गई दवाइयों और देखभाल की दिनचर्या के लिए एक जगह। शेड्यूल से जोड़ने की सुविधा आगे आएगी।','MAKE SPACE FOR YOUR HEALTH':'अपनी सेहत के लिए समय निकालें',
  'A SMALL STEP TOWARD UNDERSTANDING':'बेहतर समझ की ओर एक छोटा कदम','Your prescription. Made clearer.':'आपका प्रिस्क्रिप्शन। अब ज़्यादा स्पष्ट।','Medicines OCR · Python API required':'दवाइयों का OCR · Python API आवश्यक',
  'Upload your image':'तस्वीर अपलोड करें','Choose a clear prescription photo or take a new one.':'प्रिस्क्रिप्शन की साफ़ तस्वीर चुनें या नई तस्वीर लें।','Review every detail':'हर जानकारी जाँचें','Check extracted text, correct errors and keep unknowns visible.':'निकाले गए पाठ को जाँचें, गलतियाँ सुधारें और अज्ञात जानकारी को स्पष्ट रहने दें।','Confirm, then understand':'पुष्टि करें, फिर समझें','Save and explicitly confirm medicines before requesting an explanation.':'व्याख्या माँगने से पहले दवाइयों को सहेजें और उनकी स्पष्ट पुष्टि करें।',
  'YOUR HEALTH. YOUR PACE.':'आपकी सेहत। आपकी गति।','A little less confusion.':'थोड़ी कम उलझन।','A little more confidence.':'थोड़ा ज़्यादा भरोसा।','Start with a prescription. Stay in control of every detail.':'प्रिस्क्रिप्शन से शुरुआत करें। हर जानकारी पर आपका नियंत्रण रहे।','Explore MediSaathi':'MediSaathi देखें','Language explanation options planned':'प्रिस्क्रिप्शन की व्याख्या के लिए प्रस्तावित भाषाएँ','Understand.':'समझें।','Apni sehat, samjhein.':'अपनी सेहत को समझें।','English · Hindi · Hinglish explanations':'अंग्रेज़ी · हिंदी · हिंग्लिश में व्याख्या','Available once the AI backend is connected.':'AI बैकएंड जुड़ने पर उपलब्ध।','Your health, understood.':'आपकी सेहत, बेहतर समझ के साथ।','An educational and information tool, not medical advice.':'शिक्षा और जानकारी का साधन; चिकित्सकीय सलाह नहीं।','Always verify prescription details with your healthcare professional.':'प्रिस्क्रिप्शन की जानकारी की पुष्टि हमेशा अपने स्वास्थ्य विशेषज्ञ से करें।','Handwriting extraction is experimental.':'हस्तलिखित पाठ निकालने की सुविधा प्रायोगिक है।','MADE WITH CARE, FOR INDIA':'भारत के लिए, ध्यान से बनाया गया','MediSaathi home':'MediSaathi मुख्य पृष्ठ','YOUR HEALTH COMPANION':'आपकी सेहत का साथी','Skip to main content':'मुख्य सामग्री पर जाएँ',
  'Loading anatomy…':'शरीर रचना लोड हो रही है…','Explore your anatomy':'शरीर रचना समझें','Educational model — not a diagnosis.':'शैक्षिक मॉडल — यह निदान नहीं है।','Move pointer to turn; drag to explore.':'पॉइंटर से घुमाएँ; और देखने के लिए खींचें।','Reset view':'दृश्य रीसेट करें','3D unavailable. Explore organs below.':'3D उपलब्ध नहीं है। नीचे अंगों की जानकारी देखें।','Simplified 3D anatomy':'सरल 3D शरीर रचना','Select an organ':'अंग चुनें','Brain':'मस्तिष्क','Heart':'हृदय','Lungs':'फेफड़े','Liver':'यकृत','Stomach':'आमाशय','Kidneys':'गुर्दे','Intestines':'आँतें',
  'Coordinates thought, movement and many body functions.':'सोचने, चलने और शरीर के कई कार्यों का समन्वय करता है।','Pumps blood throughout the body.':'शरीर में रक्त का संचार करता है।','Exchange oxygen and carbon dioxide during breathing.':'साँस लेते समय ऑक्सीजन और कार्बन डाइऑक्साइड का आदान-प्रदान करते हैं।','Processes nutrients and helps remove substances from blood.':'पोषक तत्वों को संसाधित करता है और रक्त से कुछ पदार्थों को हटाने में मदद करता है।','Mixes food with acid and enzymes for digestion.':'पाचन के लिए भोजन को अम्ल और एंज़ाइम से मिलाता है।','Filter blood and regulate water and salts.':'रक्त को छानते हैं और पानी व लवण का संतुलन बनाए रखते हैं।','Absorb nutrients and water and move digestive waste.':'पोषक तत्व और पानी अवशोषित करती हैं और पाचन के अपशिष्ट को आगे बढ़ाती हैं।',
}
Object.assign(hindi,workflowHindi)
Object.assign(hindi,settingsHindi)
Object.assign(hindi,scheduleHindi)
Object.assign(hindi,restoredFeaturesHindi)
Object.assign(hindi,reviewRequirementsHindi)
Object.assign(hindi,namedSlotsHindi)
Object.assign(hindi,confirmedWorkflowHindi)
Object.assign(hindi,clockSchedulingHindi)
Object.assign(hindi,patientExplanationHindi)
Object.assign(hindi,marketPricingHindi)
Object.assign(hindi,manualPlannerHindi)
Object.assign(hindi,recognitionHindi)
Object.assign(hindi,documentHindi)

/** Only frontend-owned copy may be passed here; source medical text is never translated. */
export function translate(text:unknown,values:readonly unknown[]=[]):string{
  const source=text==null?'':String(text);const trimmed=source.trim()
  const copy=current==='hi'&&Object.hasOwn(hindi,trimmed)?hindi[trimmed]:trimmed
  const formatted=copy.replace(/\{(\d+)\}/g,(_match,index)=>String(values[Number(index)]??''))
  return (source.match(/^\s*/)?.[0]??'')+formatted+(source.match(/\s*$/)?.[0]??'')
}

const errorHindi:Record<string,string>={
  quota_exceeded:'Gemini की अनुरोध या उपयोग सीमा पूरी हो गई है। अपने-आप दोबारा प्रयास नहीं हुआ।',
  authentication_error:'Gemini ने सर्वर की कुंजी स्वीकार नहीं की। सर्वर की सेटिंग जाँचें।',
  permission_denied:'Gemini की अनुमति उपलब्ध नहीं है। सर्वर की अनुमति और मॉडल की पहुँच जाँचें।',
  model_unavailable:'सेटिंग में चुना Gemini मॉडल या संसाधन उपलब्ध नहीं है।',
  provider_bad_request:'Gemini ने अनुरोध स्वीकार नहीं किया। सर्वर की सुरक्षित त्रुटि जानकारी जाँचें।',
  provider_error:'Gemini अनुरोध पूरा नहीं कर सका। अपने-आप दोबारा प्रयास नहीं हुआ।',
  extraction_timeout:'Gemini अनुरोध का समय समाप्त हो गया। अपने-आप दोबारा प्रयास नहीं हुआ।',
  document_validation_error:'फ़ाइल मान्य नहीं है। बिना पासवर्ड की PDF, सुरक्षित DOCX या UTF-8 TXT फ़ाइल चुनें।',
  document_limit:'फ़ाइल सीमा से बड़ी है। अधिकतम 10 MiB, PDF के 3 पन्ने और पाठ के 256 KiB की सीमा है।',
  document_timeout:'PDF तैयार करने की समय सीमा समाप्त हो गई। छोटी PDF फ़ाइल चुनें।',
  explanation_unavailable:'इस समय दवा की जानकारी उपलब्ध नहीं है। कृपया सेवा की उपलब्धता जाँचें।',
  api_route_unavailable:'यह सुविधा चल रहे Python सर्वर में लोड नहीं हुई है। नया FastAPI सर्वर शुरू करें और Vite प्रॉक्सी जाँचें।',
  backend_unavailable:'सर्वर अनुरोध पूरा नहीं कर सका। कोई सफल समय-सारणी स्वीकार नहीं की गई और अपने-आप दोबारा प्रयास नहीं किया गया।',
  invalid_clock_times:'हर पुष्टि की गई खुराक के लिए अलग और सही समय चुनें। समय दिखाए गए क्रम में भरें। अतिरिक्त खुराक न जोड़ें।',
  invalid_start_date:'दवा शुरू करने की मान्य तारीख चुनें।',
  unresolved_review:'अधूरी, कम विश्वास वाली या मूल पर्चे से न मिलने वाली जानकारी की जाँच बाकी है। कोई अनुमान न लगाएँ।',
  review_required:'पहले वर्तमान जाँच सहेजें और सभी आवश्यक जानकारियों को मूल पर्चे से मिलाएँ।',
  association_exists:'यह जोड़ी पहले से पुष्टि की गई है। वर्तमान संबंध फिर लाएँ।',
  association_conflict:'चुने गए रिकॉर्ड का संबंध पहले से मौजूद है। जोड़ी बदलने से पहले संबंध स्पष्ट रूप से हटाएँ।',
  configuration_error:'AI सेवा की सेटिंग पूरी नहीं है। सर्वर की सेटिंग जाँचें।',
  quota_or_rate_limit:'AI सेवा की अनुरोध सीमा पूरी हो गई है। अपने-आप दोबारा प्रयास नहीं होगा।',
  rate_limited:'बहुत अधिक प्रयास हुए। कुछ देर बाद फिर प्रयास करें।',
  api_error:'सेवा अनुरोध पूरा नहीं कर सकी। कोई सफल परिणाम नहीं मिला।',
  network_error:'सर्वर से संपर्क नहीं हुआ। अपना कनेक्शन जाँचें।',
  image_validation_error:'तस्वीर मान्य नहीं है। साफ़, एक फ्रेम वाली PNG/JPEG तस्वीर सीमा के भीतर चुनें।',
  invalid_response:'सर्वर का परिणाम अपेक्षित प्रारूप में नहीं है। कोई नया परिणाम स्वीकार नहीं किया गया।',
  invalid_input:'भरी गई जानकारी सही प्रारूप में नहीं है। जाँचकर फिर भेजें।',
  stale_result:'यह रिकॉर्ड या संशोधन पुराना है। वर्तमान जानकारी फिर लाकर जाँचें।',
  confirmation_required:'पहले आवश्यक भागों की जाँच, सहेजना और स्पष्ट पुष्टि करें।',
  invalid_state:'यह कार्रवाई वर्तमान स्थिति में उपलब्ध नहीं है। पहले वर्तमान जानकारी देखें।',
  session_expired:'सत्र समाप्त हो गया है। फिर साइन इन करें।',
  demo_session_expired:'अस्थायी सत्र समाप्त हो गया है। नया सत्र शुरू करें।',
  no_current_prescription:'इस कार्यक्षेत्र में कोई वर्तमान पर्चा नहीं है।',
  downstream_error:'समय-सारणी की गणना पूरी नहीं हुई। कोई नई समय-सारणी उपलब्ध नहीं है।',
  unavailable:'यह सेवा अभी उपलब्ध नहीं है।',
  invalid_credentials:'ईमेल या पासवर्ड गलत है।',
  email_exists:'इस ईमेल से खाता पहले से मौजूद है। साइन इन करें।',
  storage_unavailable:'स्थानीय खाते का भंडारण अभी उपलब्ध नहीं है।',
  origin_rejected:'अनुरोध स्वीकार नहीं हुआ। कॉन्फ़िगर किए गए MediSaathi पते का उपयोग करें।',
  cookie_unavailable:'ब्राउज़र ने सत्र की कुकी नहीं रखी। कुकी सेटिंग जाँचें।',
}
export function translateError(error:unknown):string{
  const obj=error&&typeof error==='object'?error as {category?:string;message?:string}:null
  const source=obj?`${obj.category??'api_error'}: ${obj.message??''}`:String(error??'')
  if(current==='en')return source
  if(Object.hasOwn(hindi,source.trim()))return translate(source)
  const code=obj?.category??source.match(/^([a-z_]+):/)?.[1]
  const safeCode=code&&/^[a-z_]{1,64}$/.test(code)?code:null
  return (safeCode&&Object.hasOwn(errorHindi,safeCode)?errorHindi[safeCode]:'अनुरोध पूरा नहीं हुआ। कोई नया सफल परिणाम स्वीकार नहीं किया गया। वर्तमान स्थिति जाँचकर अनुमति होने पर फिर प्रयास करें।')+(safeCode?` (${safeCode})`:'')
}

/** Known warning codes are localized; original free-text uncertainty remains source evidence. */
export function translateReason(value:string):string{
  if(current!=='hi'||Object.hasOwn(hindi,value))return translate(value)
  return /^[a-z][a-z0-9_]+$/.test(value)?`अनसुलझा संकेत (${value})`:value
}

export function translateRefill(name:string,message:string):string{
  if(current!=='hi'||!message.startsWith(name+': '))return message
  const suffix=message.slice(name.length+2)
  let m=suffix.match(/^course finished on (.+)\.$/)
  if(m)return translate('{0}: course finished on {1}.',[name,m[1]])
  m=suffix.match(/^runs out on (.+)\. Time to order a refill\.$/)
  if(m)return translate('{0}: runs out on {1}. Time to order a refill.',[name,m[1]])
  m=suffix.match(/^course ends in (\d+) days? \((.+)\)\.$/)
  if(m)return translate('{0}: course ends in {1} days ({2}).',[name,m[1],m[2]])
  return message // New clinical wording is never guessed or interpreted in the browser.
}
