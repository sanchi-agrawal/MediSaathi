import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, FileScan, Pill, FlaskConical, ScanLine, CalendarDays, IndianRupee, Settings, ArrowUpRight, Menu, X, Search, ShieldCheck, ChevronRight } from 'lucide-react'
import { Badge, Brand } from './ui'

export const dashboardLinks = [
  { to:'/dashboard', label:'Overview', icon:LayoutDashboard, end:true },
  { to:'/dashboard/analysis', label:'Prescription analysis', icon:FileScan },
  { to:'/dashboard/medicines', label:'My medicines', icon:Pill },
  { to:'/dashboard/investigations', label:'Investigations', icon:FlaskConical },
  { to:'/dashboard/expiry', label:'Expiry scanner', icon:ScanLine },
  { to:'/dashboard/schedule', label:'Schedule & reminders', icon:CalendarDays },
  { to:'/dashboard/lab-costs', label:'Lab costs', icon:IndianRupee },
]
export default function DashboardLayout() {
  const [open,setOpen] = useState(false)
  const [query,setQuery] = useState('')
  const navigate = useNavigate()
  const results = dashboardLinks.filter(item=>item.label.toLowerCase().includes(query.trim().toLowerCase()))
  return <div className="dashboard-layout">{open&&<button className="sidebar-scrim" aria-label="Close navigation" onClick={()=>setOpen(false)}/>}
    <aside className={`sidebar ${open?'open':''}`}><div className="sidebar-brand"><Brand/><button className="icon-button mobile-menu" aria-label="Close navigation" onClick={()=>setOpen(false)}><X/></button></div><span className="nav-section-label">YOUR HEALTH SPACE</span><nav aria-label="Dashboard navigation">{dashboardLinks.map(({to,label,icon:Icon,end})=><NavLink end={end} key={to} to={to} onClick={()=>setOpen(false)} className={({isActive})=>isActive?'sidebar-link active':'sidebar-link'}><Icon size={19}/><span>{label}</span><ChevronRight size={13}/></NavLink>)}</nav><div className="sidebar-bottom"><div className="sidebar-care"><span className="icon-box coral"><HeartIcon/></span><h3>A little help, a clearer path.</h3><p>Check every detail with your healthcare professional.</p><Link to="/dashboard/analysis" onClick={()=>setOpen(false)}>Review a prescription <ArrowUpRight size={15}/></Link></div><NavLink to="/dashboard/settings" className="sidebar-link" onClick={()=>setOpen(false)}><Settings size={19}/>Settings</NavLink><div className="sidebar-footer"><span className="status-dot"/> FRONTEND PREVIEW <Badge tone="muted">13D</Badge></div></div></aside>
    <div className="dashboard-main"><header className="dashboard-topbar"><button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={open} onClick={()=>setOpen(true)}><Menu/></button><div className="search-wrap"><Search size={18}/><input aria-label="Find a dashboard page" placeholder="Find your way around MediSaathi…" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Escape')setQuery('');if(e.key==='Enter'&&query.trim()&&results[0]){navigate(results[0].to);setQuery('')}}}/>{query.trim()&&<div className="search-results">{results.length?results.map(item=><Link key={item.to} to={item.to} onClick={()=>setQuery('')}>{item.label}<ArrowUpRight size={14}/></Link>):<p>No matching pages.</p>}</div>}</div><div className="topbar-right"><span className="private-label"><ShieldCheck size={16}/> Public preview</span><span className="topbar-divider"/><Link className="profile-link" to="/login"><span className="avatar">G</span><span>Guest explorer<small>No account connected</small></span></Link></div></header><main className="dashboard-content" id="main-content"><Outlet/></main><footer className="dashboard-footer"><span>MediSaathi · Your health, understood.</span><span>Information tool. Always verify with a healthcare professional.</span></footer></div>
  </div>
}
function HeartIcon(){return <ShieldCheck size={23}/>}
