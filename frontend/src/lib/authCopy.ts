export const authCopy={
  login:['Sign In','साइन इन'],signup:['Sign Up','खाता बनाएँ'],forgot:['Forgot Password','पासवर्ड भूल गए'],verify:['Verify Email','ईमेल सत्यापित करें'],reset:['Reset Password','पासवर्ड बदलें'],
  name:['Full name','पूरा नाम'],email:['Email address','ईमेल पता'],password:['Password','पासवर्ड'],code:['Email verification code','ईमेल का सत्यापन कोड'],
  loading:['Checking account service…','खाता सेवा जाँची जा रही है…'],working:['Please wait…','कृपया प्रतीक्षा करें…'],logout:['Sign Out','साइन आउट'],
  setup:['Account setup unavailable. Configure Supabase on the Python server. No account has been created or authenticated.','खाता सेवा उपलब्ध नहीं है। Python सर्वर पर Supabase कॉन्फ़िगर करें। कोई खाता बनाया या प्रमाणित नहीं किया गया है।'],
  provider:['Supabase authentication','Supabase खाता सेवा'],home:['Back to home','मुख्य पृष्ठ पर वापस जाएँ'],dashboard:['Explore the demo dashboard','डेमो डैशबोर्ड देखें'],
  setupBadge:['Account setup required','खाता सेटअप आवश्यक'],
  invalid:['Enter a valid email and all required fields. New passwords need at least 12 characters; verification codes need 6–10 digits.','सही ईमेल और सभी आवश्यक फ़ील्ड भरें। नए पासवर्ड में कम से कम 12 अक्षर और सत्यापन कोड में 6–10 अंक होने चाहिए।'],
  failed:['Unable to complete this request. Check your details, email verification or server connection.','अनुरोध पूरा नहीं हुआ। अपनी जानकारी, ईमेल सत्यापन और सर्वर कनेक्शन जाँचें।'],
  limited:['Too many attempts. Please wait before trying again.','बहुत अधिक प्रयास हुए। दोबारा कोशिश करने से पहले प्रतीक्षा करें।'],
  sent:['If eligible, check your email for a verification code. Enter it on Verify Email.','यदि पात्र हैं, ईमेल में सत्यापन कोड देखें। उसे ईमेल सत्यापन पृष्ठ पर दर्ज करें।'],
  recovered:['If eligible, check your email for a recovery code, then open Reset Password.','यदि पात्र हैं, ईमेल में रिकवरी कोड देखें और पासवर्ड बदलें पृष्ठ खोलें।'],
  verified:['Email verified. You can now sign in.','ईमेल सत्यापित हो गया। अब साइन इन करें।'],resetDone:['Password changed. Sign in with the new password.','पासवर्ड बदल गया। नए पासवर्ड से साइन इन करें।'],
  show:['Show password','पासवर्ड दिखाएँ'],hide:['Hide password','पासवर्ड छिपाएँ'],notice:['Passwords are verified by Supabase. Provider credentials stay on the Python server.','पासवर्ड का सत्यापन Supabase करता है। सेवा के टोकन केवल Python सर्वर पर रहते हैं।'],
  signoutFailed:['Sign out could not reach the server. Please try again.','साइन आउट के लिए सर्वर से संपर्क नहीं हुआ। दोबारा प्रयास करें।'],
} as const
export function authText(language:'en'|'hi',key:keyof typeof authCopy){return authCopy[key][language==='hi'?1:0]}
