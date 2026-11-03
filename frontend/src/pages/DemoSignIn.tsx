import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import { useRef,useState } from 'react'
import { Link,useNavigate } from 'react-router-dom'
import { Eye,EyeOff } from 'lucide-react'
import { useLanguage } from '../lib/language'
import { demoClient,acceptDemo } from '../lib/demoAccess'
import type { DemoClient } from '../lib/demoAccess'
import AuthSplitLayout from '../components/AuthSplitLayout'
export default function DemoSignIn({client=demoClient,signup=false}:{client?:DemoClient;signup?:boolean}){
  useUiLanguage()

  const {language}=useLanguage(),navigate=useNavigate();const hi=language==='hi'
  const [show,setShow]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<'invalid'|'failed'|'name'|'mismatch'|''>('');const lock=useRef(false)
  async function submit(form:HTMLFormElement){
    if(lock.current)return
    const email=(form.elements.namedItem('email') as HTMLInputElement).value.trim()
    const field=form.elements.namedItem('demo-password') as HTMLInputElement
    const name=signup?(form.elements.namedItem('full-name') as HTMLInputElement).value.trim().replace(/\s+/g,' '):''
    const confirm=form.elements.namedItem('confirm-password') as HTMLInputElement|null
    const matches=!signup||field.value===confirm?.value
    const hasPassword=field.value.length>0
    if(confirm)confirm.value=''
    field.value='' // Clear during processing; password is never copied, sent or retained.
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||!hasPassword){setError('invalid');return}
    if(signup&&(name.length<2||name.length>100||!/[\p{L}]/u.test(name))){setError('name');return}
    if(!matches){setError('mismatch');return}
    lock.current=true;setBusy(true);setError('')
    try{const s=await (signup?client.signup(email,name):client.login(email));acceptDemo(s);form.reset();navigate('/dashboard',{replace:true})}
    catch{setError('failed')}finally{lock.current=false;setBusy(false)}
  }
  return <AuthSplitLayout><div className="auth-form-content"><span className="badge badge-coral">{hi?"डेमो प्रवेश":tr("DEMO ACCESS")}</span><h2>{signup?(hi?'डेमो प्रवेश के लिए साइन अप':'Sign Up for demo access'):(hi?'डेमो साइन इन':'Sign In to the demo')}</h2><p className="demo-login-description">{hi?"डेमो प्रवेश, सुरक्षित खाता प्रमाणीकरण नहीं। ईमेल सत्यापित नहीं है; पासवर्ड का प्रमाणीकरण नहीं होता।":tr("Demo access, not secure account authentication. Email is unverified; passwords are not authenticated.")}{signup&&<span> {hi?"इससे वास्तविक खाता नहीं बनता।":tr("This does not create an account.")}</span>}</p><form noValidate autoComplete="off" onSubmit={e=>{e.preventDefault();void submit(e.currentTarget)}}>{signup&&<label>{hi?"पूरा नाम":tr("Full Name")}<input name="full-name" required maxLength={100} autoComplete="name" disabled={busy}/></label>}<label>{hi?"ईमेल पता":tr("Email address")}<input name="email" type="email" required maxLength={254} autoComplete="off" disabled={busy}/></label><label>{hi?"पासवर्ड":tr("Password")}<div className="password-input"><input name="demo-password" type={show?'text':'password'} required autoComplete="off" disabled={busy}/><button type="button" className="icon-button" aria-label={hi?(show?'पासवर्ड छिपाएँ':'पासवर्ड दिखाएँ'):(show?'Hide password':'Show password')} onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>{signup&&<label>{hi?"पासवर्ड की पुष्टि करें":tr("Confirm Password")}<input name="confirm-password" type={show?"text":"password"} required autoComplete="off" disabled={busy}/></label>}<button type="submit" className="button full-width" disabled={busy}>{busy?(hi?'डेमो शुरू हो रहा है…':'Starting demo…'):(signup?(hi?'डेमो जारी रखें':'Continue to demo'):(hi?'साइन इन':'Sign In'))}</button>{error&&<p role="alert">{error==='name'?(hi?'कृपया अपना पूरा नाम भरें।':'Enter your full name (2–100 characters).'):error==='mismatch'?(hi?'दोनों पासवर्ड समान होने चाहिए।':'Passwords must match.'):error==='invalid'?(hi?'सही ईमेल और कोई पासवर्ड भरें।':'Enter a valid email and a nonempty password.'):(hi?'डेमो शुरू नहीं हुआ। सर्वर और ब्राउज़र कुकी जाँचकर दोबारा प्रयास करें।':'Demo session could not start. Check the server and browser cookies, then try again.')}</p>}</form><div className="demo-login-notes"><p>{hi?"केवल डेमो प्रवेश · सत्यापित ईमेल, सहेजा खाता या सूचनाएँ नहीं।":tr("Demo access only · no verified email, saved account or notifications.")}</p><p>{hi?"पासवर्ड न भेजा जाता है, न सहेजा जाता है। अस्थायी डेमो सत्र लगभग 30 मिनट रहता है।":tr("The password is never sent or saved. Temporary demo access lasts up to 30 minutes.")}</p></div><div className="auth-switch">{signup?(hi?'पहले से डेमो प्रवेश है?':'Already exploring?'):(hi?'MediSaathi पर नए हैं?':'New to MediSaathi?')} <Link to={signup?'/login':'/signup'}>{signup?(hi?'साइन इन':'Sign In'):(hi?'साइन अप':'Sign Up')}</Link></div></div></AuthSplitLayout>
}
