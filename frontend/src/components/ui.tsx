import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import { useLanguage } from '../lib/language'
import { Activity, ArrowUpRight, CircleHelp, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export function Brand({ compact = false }: { compact?: boolean }) {
  useUiLanguage()

  const { t } = useLanguage()
  return <Link className="brand" to="/" aria-label={t("MediSaathi home")}><span className="brand-icon"><Activity size={23} strokeWidth={2.5} /></span>{!compact && <span>Medi<span className="text-coral">Saathi</span><small>{t("YOUR HEALTH COMPANION")}</small></span>}</Link>
}
export function Badge({ children, tone = 'blue' }: { children: ReactNode; tone?: 'blue' | 'coral' | 'green' | 'muted' }) {
  useUiLanguage()

  return <span className={`badge badge-${tone}`}>{children}</span>
}
export function Notice({ children }: { children: ReactNode }) {
  useUiLanguage()

  return <div className="notice"><ShieldCheck size={18} /><span>{children}</span></div>
}
export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: ReactNode; description: string; action?: ReactNode }) {
  useUiLanguage()

  return <div className="page-heading"><div><span className="eyebrow">{tr(eyebrow)}</span><h1>{typeof title==='string'?tr(title):title}</h1><p>{tr(description)}</p></div>{action}</div>
}
export function EmptyState({ title, children, icon = <CircleHelp size={26} />, link }: { title: string; children: ReactNode; icon?: ReactNode; link?: string }) {
  useUiLanguage()

  return <div className="empty-state"><span className="empty-icon">{icon}</span><h3>{tr(title)}</h3><p>{children}</p>{link && <Link className="text-link" to={link}>{tr("Open prescription analysis ")}<ArrowUpRight size={15} /></Link>}</div>
}
