import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Eye, EyeOff, HeartHandshake, ShieldCheck } from 'lucide-react'
import { Badge, Brand } from '../components/ui'
import { authClient } from '../lib/api'

export default function Auth({ signup = false }: { signup?: boolean }) {
  const [show, setShow] = useState(false)
  const [message, setMessage] = useState('')
  return <main className="auth-page" id="main-content"><div className="auth-story"><Brand/><div><span className="eyebrow">A COMPANION FOR YOUR CARE</span><h1>Your health.<br/>Your understanding.<br/><span>Your next chapter.</span></h1><p>Make room for a clearer relationship with your healthcare. One prescription, one detail, one step at a time.</p><div className="auth-emblem"><HeartHandshake size={88} strokeWidth={.8}/><span className="emblem-ring"/><span className="emblem-ring second"/></div></div><span className="auth-bottom"><ShieldCheck size={17}/> Thoughtful care starts with informed choices.</span></div><div className="auth-form-side"><Link to="/" className="back-link"><ArrowLeft size={16}/> Back to home</Link><div className="auth-form-content"><Badge tone="coral">UI PREVIEW · NO AUTHENTICATION</Badge><h2>{signup?'Start your health journey.':'Welcome back.'}</h2><p>{signup?'A calmer space for your everyday healthcare.':'A little clarity is a good place to start.'}</p><form onSubmit={e=>{e.preventDefault();setMessage('The form is valid. Account services are not connected; no account or session was created.')}}>
      {signup && <label>Full name<input name="name" autoComplete="name" placeholder="Your full name" required minLength={2} maxLength={100}/></label>}
      <label>Email address<input name="email" type="email" autoComplete="email" placeholder="you@example.com" required maxLength={254}/></label>
      <label>Password<div className="password-input"><input name="password" type={show?'text':'password'} autoComplete={signup?'new-password':'current-password'} placeholder={signup?'At least 8 characters':'Enter your password'} required minLength={8} maxLength={128}/><button type="button" className="icon-button" onClick={()=>setShow(!show)} aria-label={show?'Hide password':'Show password'}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
      {signup && <label className="checkbox-label"><input type="checkbox" required/> I understand this is a UI preview and does not create an account.</label>}
      <button className="button full-width" type="submit">Validate {signup?'sign-up':'sign-in'} form <ArrowRight size={17}/></button><p className="form-footnote">{authClient.connected?'Account service available.':'Demo only. Credentials are not sent or saved.'}</p>{message&&<div className="notice" role="status">{message}</div>}
    </form><div className="auth-switch">{signup?'Already have an account?':'New to MediSaathi?'} <Link to={signup?'/login':'/signup'}>{signup?'Sign in':'Explore sign up'}</Link></div><Link className="button secondary full-width" to="/dashboard">Explore the public dashboard <ArrowRight size={16}/></Link></div><p className="auth-disclaimer">Educational information only. Not a substitute for professional medical advice.</p></div></main>
}
