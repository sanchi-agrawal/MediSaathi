import { useSyncExternalStore } from 'react'
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
  return { language, setLanguage, t: (text: string) => language === 'hi' ? hindi[text] ?? text : text }
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
  'Investigations':'जाँचें','A dedicated space for tests written on your prescription. Verify the original wording before proceeding.':'प्रिस्क्रिप्शन पर लिखी जाँचों के लिए अलग जगह। आगे बढ़ने से पहले मूल शब्दों की पुष्टि करें।','SEE THE FULL PICTURE':'पूरी जानकारी देखें',
  'Medicine expiry scanner':'दवा की एक्सपायरी स्कैनर','Upload a medicine-strip image to review visible expiry information. Missing dates stay unknown.':'दवा की स्ट्रिप की तस्वीर अपलोड करके दिख रही एक्सपायरी जानकारी जाँचें। जो तारीख दिखाई नहीं देती, वह अज्ञात रहती है।','CHECK THE SMALL PRINT':'बारीक लिखी जानकारी जाँचें',
  'Medicine management':'दवाइयों का प्रबंधन','A home for reviewed medicines and your care routine. Schedule integration is coming next.':'जाँची गई दवाइयों और देखभाल की दिनचर्या के लिए एक जगह। शेड्यूल से जोड़ने की सुविधा आगे आएगी।','MAKE SPACE FOR YOUR HEALTH':'अपनी सेहत के लिए समय निकालें',
  'Lab costs':'लैब जाँच का खर्च','A prepared space for test-cost comparisons, ready for verified pricing integration.':'जाँच के खर्च की तुलना के लिए तैयार जगह। सत्यापित कीमतें जोड़ने की सुविधा की तैयारी है।','PRICING INTEGRATION PLANNED':'कीमतें जोड़ने की योजना है',
  'A SMALL STEP TOWARD UNDERSTANDING':'बेहतर समझ की ओर एक छोटा कदम','Your prescription. Made clearer.':'आपका प्रिस्क्रिप्शन। अब ज़्यादा स्पष्ट।','Medicines OCR · Python API required':'दवाइयों का OCR · Python API आवश्यक',
  'Upload your image':'तस्वीर अपलोड करें','Choose a clear prescription photo or take a new one.':'प्रिस्क्रिप्शन की साफ़ तस्वीर चुनें या नई तस्वीर लें।','Review every detail':'हर जानकारी जाँचें','Check extracted text, correct errors and keep unknowns visible.':'निकाले गए पाठ को जाँचें, गलतियाँ सुधारें और अज्ञात जानकारी को स्पष्ट रहने दें।','Confirm, then understand':'पुष्टि करें, फिर समझें','Save and explicitly confirm medicines before requesting an explanation.':'व्याख्या माँगने से पहले दवाइयों को सहेजें और उनकी स्पष्ट पुष्टि करें।',
  'YOUR HEALTH. YOUR PACE.':'आपकी सेहत। आपकी गति।','A little less confusion.':'थोड़ी कम उलझन।','A little more confidence.':'थोड़ा ज़्यादा भरोसा।','Start with a prescription. Stay in control of every detail.':'प्रिस्क्रिप्शन से शुरुआत करें। हर जानकारी पर आपका नियंत्रण रहे।','Explore MediSaathi':'MediSaathi देखें','Language explanation options planned':'प्रिस्क्रिप्शन की व्याख्या के लिए प्रस्तावित भाषाएँ','Understand.':'समझें।','Apni sehat, samjhein.':'अपनी सेहत को समझें।','English · Hindi · Hinglish explanations':'अंग्रेज़ी · हिंदी · हिंग्लिश में व्याख्या','Available once the AI backend is connected.':'AI बैकएंड जुड़ने पर उपलब्ध।','Your health, understood.':'आपकी सेहत, बेहतर समझ के साथ।','An educational and information tool, not medical advice.':'शिक्षा और जानकारी का साधन; चिकित्सकीय सलाह नहीं।','Always verify prescription details with your healthcare professional.':'प्रिस्क्रिप्शन की जानकारी की पुष्टि हमेशा अपने स्वास्थ्य विशेषज्ञ से करें।','Handwriting extraction is experimental.':'हस्तलिखित पाठ निकालने की सुविधा प्रायोगिक है।','MADE WITH CARE, FOR INDIA':'भारत के लिए, ध्यान से बनाया गया','MediSaathi home':'MediSaathi मुख्य पृष्ठ','YOUR HEALTH COMPANION':'आपकी सेहत का साथी','Skip to main content':'मुख्य सामग्री पर जाएँ',
  'Loading anatomy…':'शरीर रचना लोड हो रही है…','Explore your anatomy':'शरीर रचना समझें','Educational model — not a diagnosis.':'शैक्षिक मॉडल — यह निदान नहीं है।','Move pointer to turn; drag to explore.':'पॉइंटर से घुमाएँ; और देखने के लिए खींचें।','Reset view':'दृश्य रीसेट करें','3D unavailable. Explore organs below.':'3D उपलब्ध नहीं है। नीचे अंगों की जानकारी देखें।','Simplified 3D anatomy':'सरल 3D शरीर रचना','Select an organ':'अंग चुनें','Brain':'मस्तिष्क','Heart':'हृदय','Lungs':'फेफड़े','Liver':'यकृत','Stomach':'आमाशय','Kidneys':'गुर्दे','Intestines':'आँतें',
  'Coordinates thought, movement and many body functions.':'सोचने, चलने और शरीर के कई कार्यों का समन्वय करता है।','Pumps blood throughout the body.':'शरीर में रक्त का संचार करता है।','Exchange oxygen and carbon dioxide during breathing.':'साँस लेते समय ऑक्सीजन और कार्बन डाइऑक्साइड का आदान-प्रदान करते हैं।','Processes nutrients and helps remove substances from blood.':'पोषक तत्वों को संसाधित करता है और रक्त से कुछ पदार्थों को हटाने में मदद करता है।','Mixes food with acid and enzymes for digestion.':'पाचन के लिए भोजन को अम्ल और एंज़ाइम से मिलाता है।','Filter blood and regulate water and salts.':'रक्त को छानते हैं और पानी व लवण का संतुलन बनाए रखते हैं।','Absorb nutrients and water and move digestive waste.':'पोषक तत्व और पानी अवशोषित करती हैं और पाचन के अपशिष्ट को आगे बढ़ाती हैं।',
}
