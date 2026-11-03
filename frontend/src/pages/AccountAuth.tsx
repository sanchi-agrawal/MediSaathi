import AuthSplitLayout from '../components/AuthSplitLayout'
import { useRef,useState } from 'react'
import { Link,useNavigate } from 'react-router-dom'
import { Eye,EyeOff } from 'lucide-react'
import { useLanguage } from '../lib/language'
import { authText } from '../lib/authCopy'
import { accountClient,setAccountUser,useAccount } from '../lib/accounts'
import type { AccountClient } from '../lib/accounts'
import { ApiError } from '../lib/prescriptions'
type Mode='login'|'signup'|'forgot'|'verify'|'reset'
export default function AccountAuth({mode='login',client=accountClient,available}:{mode?:Mode;client?:AccountClient;available?:boolean}){
  const status=useAccount(),{language}=useLanguage(),navigate=useNavigate();const [show,setShow]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<Parameters<typeof authText>[1]|''>(''),[message,setMessage]=useState<Parameters<typeof authText>[1]|''>('');const lock=useRef(false)
  const text=(key:Parameters<typeof authText>[1])=>authText(language,key)
  const enabled=available??(status.configured&&!status.loading&&!status.error)
  async function submit(form:HTMLFormElement){
    if(lock.current||!enabled)return
    const values=new FormData(form),email=String(values.get('email')??'').trim(),password=String(values.get('password')??''),name=String(values.get('name')??'').trim(),code=String(values.get('code')??'').trim()
    setError('');setMessage('')
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||(mode==='signup'&&name.length<2)||(['login','signup','reset'].includes(mode)&&(!password||password.length>128))||(['signup','reset'].includes(mode)&&password.length<12)||(['verify','reset'].includes(mode)&&!/^\d{6,10}$/.test(code))){setError('invalid');return}
    lock.current=true;setBusy(true)
    try{
      if(mode==='login'){const user=await client.login(email,password);setAccountUser(user);navigate('/dashboard',{replace:true})}
      else if(mode==='signup'){await client.signup(name,email,password);form.reset();setMessage('sent')}
      else if(mode==='forgot'){await client.forgot(email);setMessage('recovered')}
      else if(mode==='verify'){await client.verify(email,code);form.reset();setMessage('verified')}
      else {await client.reset(email,code,password);form.reset();setMessage('resetDone')}
    }catch(e){setError(e instanceof ApiError&&e.category==='rate_limited'?'limited':'failed')}finally{setBusy(false);lock.current=false}
  }
  return <AuthSplitLayout><div className="auth-form-content"><span className="badge">{enabled?text('provider'):text('setupBadge')}</span><h2>{text(mode)}</h2>{available===undefined&&status.loading?<p role="status">{text('loading')}</p>:!enabled&&<p role="status">{text('setup')}</p>}<form noValidate onSubmit={e=>{e.preventDefault();void submit(e.currentTarget)}}>
    {mode==='signup'&&<label>{text('name')}<input name="name" autoComplete="name" required minLength={2} maxLength={100} disabled={!enabled||busy}/></label>}
    <label>{text('email')}<input name="email" type="email" autoComplete="email" required maxLength={254} disabled={!enabled||busy}/></label>
    {['verify','reset'].includes(mode)&&<label>{text('code')}<input name="code" autoComplete="one-time-code" inputMode="numeric" required minLength={6} maxLength={10} disabled={!enabled||busy}/></label>}
    {['login','signup','reset'].includes(mode)&&<label>{text('password')}<div className="password-input"><input name="password" type={show?'text':'password'} autoComplete={mode==='login'?'current-password':'new-password'} required minLength={mode==='login'?1:12} maxLength={128} disabled={!enabled||busy}/><button type="button" className="icon-button" aria-label={text(show?'hide':'show')} onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>}
    <button className="button full-width" type="submit" disabled={!enabled||busy}>{text(busy?'working':mode)}</button>{error&&<p role="alert">{text(error)}</p>}{message&&<div className="notice" role="status">{text(message)}</div>}</form><div className="auth-switch"><Link to="/login">{text('login')}</Link> · <Link to="/signup">{text('signup')}</Link></div><p><Link to="/forgot-password">{text('forgot')}</Link> · <Link to="/reset-password">{text('reset')}</Link> · <Link to="/verify-email">{text('verify')}</Link></p>{!status.configured&&<Link to="/dashboard">{text('dashboard')}</Link>}</div></AuthSplitLayout>
}
