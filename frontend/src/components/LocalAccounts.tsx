import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import { Fragment,useRef,useState } from 'react'
import type { ReactNode } from 'react'
import { Link,Navigate,useNavigate,useLocation } from 'react-router-dom'
import { Eye,EyeOff } from 'lucide-react'
import AuthSplitLayout from './AuthSplitLayout'
import { useLanguage } from '../lib/language'
import { localClient,setLocalUser,useLocalAccount,refreshLocal,announceLocalChange } from '../lib/localAccounts'
import type { LocalClient } from '../lib/localAccounts'
import { ApiError } from '../lib/prescriptions'
import { validNewPassword,MIN_PASSWORD_LENGTH,MAX_PASSWORD_LENGTH } from '../lib/passwordPolicy'

const messages:Record<string,[string,string]>={
  invalid_input:['Enter a valid email and password.','सही ईमेल और पासवर्ड भरें।'],
  password_policy:['Password must contain at least 6 characters.','पासवर्ड कम से कम 6 अक्षरों का होना चाहिए।'],
  name:['Enter your full name (2–100 characters).','अपना पूरा नाम भरें (2–100 अक्षर)।'],
  mismatch:['Passwords must match.','दोनों पासवर्ड समान होने चाहिए।'],
  email_exists:['An account with this email already exists. Sign in instead.','इस ईमेल से खाता पहले से मौजूद है। साइन इन करें।'],
  invalid_credentials:['Email or password is incorrect.','ईमेल या पासवर्ड गलत है।'],
  rate_limited:['Too many attempts. Please try again later.','बहुत अधिक प्रयास हुए। कुछ देर बाद फिर कोशिश करें।'],
  failed:['Unable to complete the request. Check the local server and browser cookies.','अनुरोध पूरा नहीं हुआ। स्थानीय सर्वर और ब्राउज़र कुकी जाँचें।'],
}
export function LocalAuth({signup=false,client=localClient}:{signup?:boolean;client?:LocalClient}){
  useUiLanguage()

  const {language}=useLanguage();const hi=language==='hi';const navigate=useNavigate();const location=useLocation()
  const [busy,setBusy]=useState(false),[show,setShow]=useState(false),[error,setError]=useState('');const lock=useRef(false)
  async function submit(form:HTMLFormElement){
    if(lock.current)return
    const email=(form.elements.namedItem('email') as HTMLInputElement).value.trim()
    const field=form.elements.namedItem('password') as HTMLInputElement
    let password=field.value;field.value=''
    const confirm=form.elements.namedItem('confirm') as HTMLInputElement|null
    const matches=!signup||password===confirm?.value;if(confirm)confirm.value=''
    const name=signup?(form.elements.namedItem('name') as HTMLInputElement).value.trim().replace(/\s+/g,' '):''
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||password.length<1||password.length>128){password='';setError('invalid_input');return}
    if(signup&&!validNewPassword(password)){password='';setError('password_policy');return}
    if(signup&&(name.length<2||name.length>100||!/[\p{L}]/u.test(name))){password='';setError('name');return}
    if(!matches){password='';setError('mismatch');return}
    lock.current=true;setBusy(true);setError('')
    try{
      const request=signup?client.signup(name,email,password):client.login(email,password)
      password=''
      const user=await request;setLocalUser(user);announceLocalChange();form.reset();navigate('/dashboard',{replace:true})
    }catch(e){setError(e instanceof ApiError&&messages[e.category]?e.category:'failed')}
    finally{password='';lock.current=false;setBusy(false)}
  }
  return <AuthSplitLayout><div className="auth-form-content">
    <span className="badge badge-coral">{hi?"स्थानीय खाता":tr("LOCAL ACCOUNT")}</span>
    <h2>{signup?(hi?'खाता बनाएँ':'Create Account'):(hi?'साइन इन':'Sign In')}</h2>
    <p className="demo-login-description">{hi?"आपका खाता इस कंप्यूटर पर सहेजा जाता है। ईमेल का सत्यापन नहीं होता।":tr("Your account is saved on this computer. Email ownership is not verified.")}</p>
    {location.state?.passwordChanged&&<p role="status">{tr('Password changed. Sign in again.')}</p>}{location.state?.accountDeleted&&<p role="status">{tr('Your local account was deleted.')}</p>}<form noValidate onSubmit={e=>{e.preventDefault();void submit(e.currentTarget)}}>
      {signup&&<label>{hi?"पूरा नाम":tr("Full Name")}<input name="name" autoComplete="name" required maxLength={100} disabled={busy}/></label>}
      <label>{hi?"ईमेल पता":tr("Email Address")}<input name="email" type="email" autoComplete="username" required maxLength={254} disabled={busy}/></label>
      <label>{hi?"पासवर्ड":tr("Password")}<div className="password-input"><input name="password" minLength={signup?MIN_PASSWORD_LENGTH:1} type={show?'text':'password'} autoComplete={signup?'new-password':'current-password'} required maxLength={MAX_PASSWORD_LENGTH} disabled={busy}/><button className="icon-button" type="button" aria-label={hi?(show?'पासवर्ड छिपाएँ':'पासवर्ड दिखाएँ'):(show?'Hide password':'Show password')} onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
      {signup&&<small>{tr('Password must contain at least 6 characters.')} {tr('Up to 128 characters; passphrases are welcome.')}</small>}{signup&&<label>{hi?"पासवर्ड की पुष्टि करें":tr("Confirm Password")}<input name="confirm" type={show?'text':'password'} autoComplete="new-password" required maxLength={MAX_PASSWORD_LENGTH} disabled={busy}/></label>}
      <button className="button full-width" disabled={busy}>{busy?(hi?'कृपया प्रतीक्षा करें…':'Please wait…'):(signup?(hi?'खाता बनाएँ':'Create Account'):(hi?'साइन इन':'Sign In'))}</button>
      {error&&<p role="alert">{(messages[error]||messages.failed)[hi?1:0]}</p>}
    </form>
    <div className="demo-login-notes"><p>{hi?"पर्चे केवल अस्थायी कार्यक्षेत्र में रहते हैं। लॉग आउट, सत्र समाप्ति या सर्वर बंद होने पर हट जाते हैं। वास्तविक रोगी डेटा उपयोग न करें।":tr("Prescriptions remain in a temporary workspace, cleared on logout, workspace expiry or server restart. Use no real patient data.")}</p><p>{hi?"पासवर्ड सुरक्षित हैश के रूप में सहेजे जाते हैं। ईमेल सत्यापन और पासवर्ड पुनर्प्राप्ति उपलब्ध नहीं हैं।":tr("Passwords are stored as secure hashes. Email verification and password recovery are unavailable.")}</p></div>
    <div className="auth-switch"><Link to={signup?'/login':'/signup'}>{signup?(hi?'साइन इन':'Sign In'):(hi?'साइन अप':'Sign Up')}</Link></div>
  </div></AuthSplitLayout>
}
export function LocalAccess({children,allowDemo=false}:{children:ReactNode;allowDemo?:boolean}){
  useUiLanguage()

  const s=useLocalAccount();const {language}=useLanguage();const hi=language==='hi'
  if(s.loading)return <p role="status">{hi?"सत्र जाँचा जा रहा है…":tr("Checking session…")}</p>
  if(s.error)return <p role="alert">{hi?"स्थानीय सर्वर उपलब्ध नहीं है।":tr("Local server unavailable.")}<button onClick={()=>void refreshLocal()}>{hi?"फिर जाँचें":tr("Check again")}</button></p>
  if(!s.user)return <Navigate to="/login" replace/>
  return <Fragment key={s.user.id}>{allowDemo?children:<p className="notice">{hi?"पर्चों का स्थायी इतिहास उपलब्ध नहीं है। वर्तमान अस्थायी कार्यक्षेत्र का उपयोग करें।":tr("Durable prescription history is unavailable. Use the current temporary workspace.")}</p>}</Fragment>
}
export function LocalProfile({onSignedOut=()=>window.location.assign('/login')}:{onSignedOut?:()=>void}){
  useUiLanguage()

  const s=useLocalAccount();const {language}=useLanguage();const hi=language==='hi'
  const [busy,setBusy]=useState(false),[error,setError]=useState(false);const lock=useRef(false)
  if(!s.user)return null
  const user=s.user;const initials=user.full_name.split(/\s+/).slice(0,2).map(s=>Array.from(s)[0]).join('').toLocaleUpperCase()
  async function logout(){if(lock.current)return;lock.current=true;setBusy(true);try{await localClient.logout();setLocalUser(null);announceLocalChange();onSignedOut()}catch{setError(true);setBusy(false)}finally{lock.current=false}}
  return <><details className="demo-profile"><summary><span className="avatar" aria-hidden="true">{initials}</span><span>{user.full_name}</span></summary><div className="demo-profile-menu"><strong>{user.full_name}</strong><small>{user.email}</small><Link to="/dashboard/settings">{tr("Settings")}</Link><small>{hi?"स्थानीय खाता · ईमेल सत्यापित नहीं":tr("Local account · email not verified")}</small></div></details><button className="button secondary small" disabled={busy} onClick={()=>void logout()}>{hi?"लॉग आउट":tr("Log Out")}</button>{error&&<span role="alert">{hi?"लॉग आउट पूरा नहीं हुआ। फिर कोशिश करें।":tr("Logout failed. Please try again.")}</span>}</>
}
export function LocalRecovery(){
  useUiLanguage()
const {language}=useLanguage();return <AuthSplitLayout><h2>{language==='hi'?"यह सुविधा उपलब्ध नहीं है":tr("This feature is unavailable")}</h2><p>{language==='hi'?"स्थानीय खाते में ईमेल सत्यापन या पासवर्ड पुनर्प्राप्ति नहीं है।":tr("Local accounts do not support email verification or password recovery.")}</p><Link to="/login">{language==='hi'?"साइन इन":tr("Sign In")}</Link></AuthSplitLayout>}
export { default as LocalSettings } from '../pages/Settings'
