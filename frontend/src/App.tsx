import { useLanguage as useUiLanguage, translate as tr } from './lib/language'
import { LOCAL_AUTH } from './lib/localAccounts'
import { LocalRecovery,LocalSettings } from './components/LocalAccounts'
import { useLanguage } from './lib/language'
import { Route, Routes, Link, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Landing from './pages/Landing'
import { SessionAuth as Auth } from './components/SessionAccess'
import DashboardLayout from './components/DashboardLayout'
import Overview from './pages/Overview'
import Analysis from './pages/PrescriptionFlow'
import Schedule from './pages/ManualSchedule'
import CurrentWorkspace from './pages/CurrentWorkspace'
import { Settings } from './pages/Workspace'
import ExpiryScanner from './pages/ExpiryScanner'
import Pricing from './pages/MarketPricing'
import OfflineDemoNotice from './components/OfflineDemoNotice'
import { SessionAccess as AccountAccess } from './components/SessionAccess'
import AccountAuth from './pages/AccountAuth'
import MyPrescriptions from './pages/MyPrescriptions'

function RouteEffects(){
  useUiLanguage()
const {language}=useLanguage();const {pathname}=useLocation();useEffect(()=>{window.scrollTo(0,0);document.title=`${tr(pathname.includes('dashboard')?'Dashboard':pathname.includes('signup')?'Sign up':pathname.includes('login')?'Sign in':'Your health, understood.')} · MediSaathi`;document.getElementById('main-content')?.setAttribute('tabindex','-1');document.getElementById('main-content')?.focus({preventScroll:true})},[pathname,language]);return null}
export default function App(){
  useUiLanguage()
const {t}=useLanguage();return <><OfflineDemoNotice/><a className="skip-link" href="#main-content">{t("Skip to main content")}</a><RouteEffects/><Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<Auth/>}/><Route path="/signup" element={<Auth signup/>}/><Route path="/forgot-password" element={LOCAL_AUTH?<LocalRecovery/>:<AccountAuth mode="forgot"/>}/><Route path="/verify-email" element={LOCAL_AUTH?<LocalRecovery/>:<AccountAuth mode="verify"/>}/><Route path="/reset-password" element={LOCAL_AUTH?<LocalRecovery/>:<AccountAuth mode="reset"/>}/><Route path="/dashboard" element={<AccountAccess allowDemo><DashboardLayout/></AccountAccess>}><Route index element={<Overview/>}/><Route path="prescriptions" element={<AccountAccess><MyPrescriptions/></AccountAccess>}/><Route path="analysis" element={<Analysis/>}/><Route path="medicines" element={<CurrentWorkspace kind="medicines"/>}/><Route path="investigations/*" element={<Navigate to="/dashboard/analysis" replace/>}/><Route path="expiry/*" element={<Navigate to="/dashboard/strip-expiry" replace/>}/><Route path="strip-expiry" element={<ExpiryScanner/>}/><Route path="schedule" element={<Schedule/>}/><Route path="lab-costs/*" element={<Navigate to="/dashboard" replace/>}/><Route path="medicine-pricing" element={<Pricing/>}/><Route path="settings" element={LOCAL_AUTH?<LocalSettings/>:<Settings/>}/></Route><Route path="*" element={<main className="not-found" id="main-content"><span className="eyebrow">{tr("404 · A LITTLE OFF THE PATH")}</span><h1>{tr("Let’s get you back.")}</h1><p>{tr("This page could not be found.")}</p><Link className="button" to="/">{tr("Back to MediSaathi")}</Link></main>}/></Routes></>}
