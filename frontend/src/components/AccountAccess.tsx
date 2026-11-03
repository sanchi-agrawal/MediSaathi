import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import type { ReactNode } from 'react'
import { Navigate,useLocation,Link } from 'react-router-dom'
import { useAccount,accountClient,setAccountUser } from '../lib/accounts'
import { useLanguage } from '../lib/language'
import { authText } from '../lib/authCopy'
import { useState } from 'react'
import { Fragment } from 'react'
import { initials } from './Personalization'
export function AccountAccess({children,allowDemo=false}:{children:ReactNode;allowDemo?:boolean}){
  useUiLanguage()

  const s=useAccount();const {language}=useLanguage();const location=useLocation()
  if(s.loading)return <main className="notice">{authText(language,'loading')}</main>
  if(s.error)return <main className="notice" role="alert">{authText(language,'failed')}</main>
  if(!s.configured)return allowDemo?<>{children}</>:<main className="notice">{authText(language,'setup')}</main>
  if(!s.user)return <Navigate to="/login" replace state={{from:location.pathname}}/>
  return <Fragment key={s.user.id}>{children}</Fragment>
}
export function AccountProfile(){
  useUiLanguage()

  const s=useAccount();const {language}=useLanguage();const [busy,setBusy]=useState(false),[error,setError]=useState(false)
  if(!s.user)return <Link to="/login">{authText(language,'login')}{!s.configured&&<small>{tr(" · Demo")}</small>}</Link>
  async function signOut(){
    setBusy(true);setError(false)
    try{await accountClient.logout();setAccountUser(null);window.location.assign('/login')}
    catch{setError(true);setBusy(false)}
  }
  return <><span className="profile-link"><span className="avatar" aria-hidden="true">{initials(s.user.name)}</span><span>{s.user.name ?? s.user.email}<small>{s.user.email}</small></span></span><button className="button secondary small" disabled={busy} onClick={()=>void signOut()}>{authText(language,busy?'working':'logout')}</button>{error&&<span role="alert">{authText(language,'signoutFailed')}</span>}</>
}
export function AccountMode(){
  useUiLanguage()
const s=useAccount();return <span>{s.user?tr("Account workspace"):tr("Demo workspace · no account")}</span>}
