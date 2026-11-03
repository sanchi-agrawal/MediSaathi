import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import type { ReactNode } from 'react'
import { useRef,useState } from 'react'
import { Navigate } from 'react-router-dom'
import { AccountAccess,AccountProfile,AccountMode } from './AccountAccess'
import Auth from '../pages/Auth'
import DemoSignIn from '../pages/DemoSignIn'
import { DEMO_ACCESS,useDemoAccess,demoClient,clearDemo,refreshDemo } from '../lib/demoAccess'
import { useLanguage } from '../lib/language'
import { initials } from './Personalization'
import { LOCAL_AUTH } from '../lib/localAccounts'
import { LocalAuth,LocalAccess,LocalProfile } from './LocalAccounts'
export function DemoAccess({children}:{children:ReactNode}){
  useUiLanguage()

  const s=useDemoAccess();const {language}=useLanguage();const hi=language==='hi'
  if(s.loading)return <p role="status">{hi?"डेमो सत्र जाँचा जा रहा है…":tr("Checking demo session…")}</p>
  if(s.error)return <div className="notice" role="alert">{hi?"डेमो सर्वर उपलब्ध नहीं है।":tr("Demo server unavailable.")}<button onClick={()=>void refreshDemo()}>{hi?"दोबारा जाँचें":tr("Check again")}</button></div>
  return s.active?<>{children}</>:<Navigate to="/login" replace/>
}
export function SessionAccess({children,allowDemo=false}:{children:ReactNode;allowDemo?:boolean}){
  useUiLanguage()

  if(LOCAL_AUTH)return <LocalAccess allowDemo={allowDemo}>{children}</LocalAccess>
  if(!DEMO_ACCESS)return <AccountAccess allowDemo={allowDemo}>{children}</AccountAccess>
  return <DemoAccess>{allowDemo?children:<p className="notice">{tr("Account history is unavailable in demo access. Use fictional data only.")}</p>}</DemoAccess>
}
export function SessionAuth({signup=false}:{signup?:boolean}){
  useUiLanguage()
return LOCAL_AUTH?<LocalAuth signup={signup}/>:DEMO_ACCESS?<DemoSignIn signup={signup}/>:<Auth signup={signup}/>}
export function DemoProfile({onSignedOut=()=>window.location.assign('/login')}:{onSignedOut?:()=>void}){
  useUiLanguage()

  const session=useDemoAccess();const name=session.active?session.displayName:null
  const {language}=useLanguage();const hi=language==='hi';const [busy,setBusy]=useState(false),[error,setError]=useState(false);const lock=useRef(false)
  async function logout(){if(lock.current)return;lock.current=true;setBusy(true);setError(false);try{await demoClient.logout();clearDemo();onSignedOut()}catch{setError(true);setBusy(false)}finally{lock.current=false}}
  return <><details className="demo-profile"><summary><span className="avatar" aria-hidden="true">{initials(name)}</span><span>{name || (hi?'डेमो प्रवेश':'Demo access')}</span></summary><div className="demo-profile-menu"><strong>{name || (hi?'डेमो प्रवेश':'Demo access')}</strong><small>{hi?"अस्थायी डेमो · सत्यापित खाता नहीं":tr("Temporary demo · not a verified account")}</small></div></details><button className="button secondary small" disabled={busy} onClick={()=>void logout()}>{hi?"लॉग आउट":tr("Log Out")}</button>{error&&<span role="alert">{hi?"लॉग आउट पूरा नहीं हुआ। दोबारा प्रयास करें।":tr("Log out failed. Please try again.")}</span>}</>
}
export function SessionProfile(){
  useUiLanguage()
return LOCAL_AUTH?<LocalProfile/>:DEMO_ACCESS?<DemoProfile/>:<AccountProfile/>}
export function SessionMode(){
  useUiLanguage()
return LOCAL_AUTH?<LocalMode/>:DEMO_ACCESS?<span>{tr("DEMO ACCESS · not account authentication")}</span>:<AccountMode/>}
function LocalMode(){
  useUiLanguage()
const {language}=useLanguage();return <span>{language==='hi'?"स्थानीय खाता · पर्चे अस्थायी":tr("Local account · temporary prescriptions")}</span>}
export function DemoDisclosure(){
  useUiLanguage()
return DEMO_ACCESS?<div className="notice">{tr("Demo access only · fictional data · no verified email, saved account or notifications.")}</div>:null}
