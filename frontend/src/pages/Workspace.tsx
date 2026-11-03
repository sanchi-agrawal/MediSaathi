import { useLanguage as useUiLanguage, translate as tr } from '../lib/language'
import { useAccount } from '../lib/accounts'
import { useState } from 'react'
import { CalendarDays, FlaskConical, Pill } from 'lucide-react'
import { Badge, EmptyState, Notice, PageHeading } from '../components/ui'

const workspaces = {
  medicines:{title:'My medicines',eyebrow:'EVERY DETAIL, TOGETHER',description:'A considered space for your confirmed medicine information.',icon:Pill,empty:'No confirmed medicines yet',body:'Review and confirm a prescription first. Medicine matching and pricing will use the existing Python integrations.'},
  investigations:{title:'Investigations',eyebrow:'SEE THE FULL PICTURE',description:'Keep prescribed tests and their original wording in view.',icon:FlaskConical,empty:'No confirmed investigations yet',body:'Investigations have a separate review and confirmation scope. No test names or variants will be inferred.'},
  schedule:{title:'Schedule & reminders',eyebrow:'CARE, AT YOUR PACE',description:'A place for your confirmed care routine.',icon:CalendarDays,empty:'Your schedule is not connected',body:'This page is reserved for Person 3’s scheduling and reminders. Dose calculations and reminder delivery are not implemented in the browser.'},
}
export function Workspace({kind}:{kind:keyof typeof workspaces}) {
  useUiLanguage()

  const item=workspaces[kind];const Icon=item.icon
  return <><PageHeading eyebrow={tr(item.eyebrow)} title={tr(item.title)} description={tr(item.description)} action={<Badge tone="muted">{tr("Integration pending")}</Badge>}/><section className="panel workspace-empty"><EmptyState title={tr(item.empty)} icon={<Icon size={34}/>} link="/dashboard/analysis">{tr(item.body)}</EmptyState></section><Notice>{tr("There is no patient data in this frontend preview. Backend actions remain unavailable until connected.")}</Notice></>
}
export { default as Expiry } from './ExpiryScanner'
export function Settings() {
  useUiLanguage()

  const account=useAccount()
  const [language,setLanguage]=useState('English')
  return <><PageHeading eyebrow={tr("MAKE YOURSELF AT HOME")} title={tr("Settings")} description={tr("A few thoughtful details for your health space.")}/><section className="panel settings-panel"><h2>{tr("Explanation preference")}</h2><p>{tr("Local preview only. This preference is not stored or sent to a server.")}</p><label>{tr("Preferred explanation language")}<select value={language} onChange={e=>setLanguage(e.target.value)}><option>English</option><option value={"Hindi"}>{tr("Hindi")}</option><option>Hinglish</option></select></label><div className="settings-row"><div><h3>{tr("Account")}</h3><p>{account.user?account.user.email:tr("No authenticated account is connected.")}</p></div><Badge tone={account.user?'green':'muted'}>{account.user?tr("Signed in"):tr("Not signed in")}</Badge></div><div className="settings-row"><div><h3>{tr("AI connection")}</h3><p>{tr("Gemini extraction stays on the Python server.")}</p></div><Badge tone="coral">{tr("Not connected")}</Badge></div><div className="settings-row"><div><h3>{tr("Accessibility")}</h3><p>{tr("Keyboard navigation and your device’s reduced-motion preference are supported.")}</p></div></div></section></>
}
