import { Route, Routes, Link, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Landing from './pages/Landing'
import Auth from './pages/Auth'
import DashboardLayout from './components/DashboardLayout'
import Overview from './pages/Overview'
import Analysis from './pages/PrescriptionFlow'
import { Expiry, Settings, Workspace } from './pages/Workspace'

function RouteEffects(){const {pathname}=useLocation();useEffect(()=>{window.scrollTo(0,0);document.title=`${pathname.includes('dashboard')?'Dashboard':pathname.includes('signup')?'Sign up':pathname.includes('login')?'Sign in':'Your health, understood.'} · MediSaathi`;document.getElementById('main-content')?.setAttribute('tabindex','-1');document.getElementById('main-content')?.focus({preventScroll:true})},[pathname]);return null}
export default function App(){return <><a className="skip-link" href="#main-content">Skip to main content</a><RouteEffects/><Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<Auth/>}/><Route path="/signup" element={<Auth signup/>}/><Route path="/dashboard" element={<DashboardLayout/>}><Route index element={<Overview/>}/><Route path="analysis" element={<Analysis/>}/><Route path="medicines" element={<Workspace kind="medicines"/>}/><Route path="investigations" element={<Workspace kind="investigations"/>}/><Route path="expiry" element={<Expiry/>}/><Route path="schedule" element={<Workspace kind="schedule"/>}/><Route path="lab-costs" element={<Workspace kind="lab-costs"/>}/><Route path="settings" element={<Settings/>}/></Route><Route path="*" element={<main className="not-found" id="main-content"><span className="eyebrow">404 · A LITTLE OFF THE PATH</span><h1>Let’s get you back.</h1><p>This page could not be found.</p><Link className="button" to="/">Back to MediSaathi</Link></main>}/></Routes></>}
