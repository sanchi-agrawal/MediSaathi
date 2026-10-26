import { useState } from 'react'
import { CalendarDays, FlaskConical, IndianRupee, Pill } from 'lucide-react'
import { Badge, EmptyState, Notice, PageHeading } from '../components/ui'

const workspaces = {
  medicines:{title:'My medicines',eyebrow:'EVERY DETAIL, TOGETHER',description:'A considered space for your confirmed medicine information.',icon:Pill,empty:'No confirmed medicines yet',body:'Review and confirm a prescription first. Medicine matching and pricing will use the existing Python integrations.'},
  investigations:{title:'Investigations',eyebrow:'SEE THE FULL PICTURE',description:'Keep prescribed tests and their original wording in view.',icon:FlaskConical,empty:'No confirmed investigations yet',body:'Investigations have a separate review and confirmation scope. No test names or variants will be inferred.'},
  schedule:{title:'Schedule & reminders',eyebrow:'CARE, AT YOUR PACE',description:'A place for your confirmed care routine.',icon:CalendarDays,empty:'Your schedule is not connected',body:'This page is reserved for Person 3’s scheduling and reminders. Dose calculations and reminder delivery are not implemented in the browser.'},
  'lab-costs':{title:'Lab costs',eyebrow:'PLAN WITH CLEARER INFORMATION',description:'A home for verified medical-test costs, once connected.',icon:IndianRupee,empty:'Verified costs are not available yet',body:'Lab costs will come from Person 2’s pricing implementation after investigation review. No estimates or sample prices are shown.'},
}
export function Workspace({kind}:{kind:keyof typeof workspaces}) {
  const item=workspaces[kind];const Icon=item.icon
  return <><PageHeading eyebrow={item.eyebrow} title={item.title} description={item.description} action={<Badge tone="muted">Integration pending</Badge>}/><section className="panel workspace-empty"><EmptyState title={item.empty} icon={<Icon size={34}/>} link="/dashboard/analysis">{item.body}</EmptyState></section><Notice>There is no patient data in this frontend preview. Backend actions remain unavailable until connected.</Notice></>
}
export { default as Expiry } from './ExpiryScanner'
export function Settings() {
  const [language,setLanguage]=useState('English')
  return <><PageHeading eyebrow="MAKE YOURSELF AT HOME" title="Settings" description="A few thoughtful details for your health space."/><section className="panel settings-panel"><h2>Explanation preference</h2><p>Local preview only. This preference is not stored or sent to a server.</p><label>Preferred explanation language<select value={language} onChange={e=>setLanguage(e.target.value)}><option>English</option><option>Hindi</option><option>Hinglish</option></select></label><div className="settings-row"><div><h3>Account</h3><p>You’re exploring a public frontend preview.</p></div><Badge tone="muted">Not signed in</Badge></div><div className="settings-row"><div><h3>AI connection</h3><p>Gemini extraction stays on the Python server.</p></div><Badge tone="coral">Not connected</Badge></div><div className="settings-row"><div><h3>Accessibility</h3><p>Keyboard navigation and your device’s reduced-motion preference are supported.</p></div></div></section></>
}
