import { Activity, ArrowUpRight, CircleHelp, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link className="brand" to="/" aria-label="MediSaathi home"><span className="brand-icon"><Activity size={23} strokeWidth={2.5} /></span>{!compact && <span>Medi<span className="text-coral">Saathi</span><small>YOUR HEALTH COMPANION</small></span>}</Link>
}
export function Badge({ children, tone = 'blue' }: { children: ReactNode; tone?: 'blue' | 'coral' | 'green' | 'muted' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}
export function Notice({ children }: { children: ReactNode }) {
  return <div className="notice"><ShieldCheck size={18} /><span>{children}</span></div>
}
export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>
}
export function EmptyState({ title, children, icon = <CircleHelp size={26} />, link }: { title: string; children: ReactNode; icon?: ReactNode; link?: string }) {
  return <div className="empty-state"><span className="empty-icon">{icon}</span><h3>{title}</h3><p>{children}</p>{link && <Link className="text-link" to={link}>Open prescription analysis <ArrowUpRight size={15} /></Link>}</div>
}
