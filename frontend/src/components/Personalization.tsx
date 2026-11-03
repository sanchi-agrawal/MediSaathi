import { DEMO_ACCESS,useDemoAccess } from '../lib/demoAccess'
import { useAccount } from '../lib/accounts'
import { useLanguage } from '../lib/language'
import { LOCAL_AUTH,useLocalAccount } from '../lib/localAccounts'

export function initials(name:string|null){return name?.trim().split(/\s+/).filter(Boolean).slice(0,2).map(s=>Array.from(s)[0]).join('').toLocaleUpperCase()||'MS'}
export function Greeting({name}:{name:string|null}){
  const {language}=useLanguage();const first=name?.trim().split(/\s+/)[0]
  return <>{first?(language==='hi'?`वापसी पर स्वागत है, ${first}!`:`Welcome back, ${first}!`):(language==='hi'?'MediSaathi में आपका स्वागत है!':'Welcome to MediSaathi!')}</>
}
function DemoGreeting(){const s=useDemoAccess();return <Greeting name={s.active?s.displayName:null}/>}
function AccountGreeting(){const s=useAccount();return <Greeting name={s.user?.name??null}/>}
function LocalGreeting(){const s=useLocalAccount();return <Greeting name={s.user?.full_name??null}/>}
export function SessionGreeting(){return LOCAL_AUTH?<LocalGreeting/>:DEMO_ACCESS?<DemoGreeting/>:<AccountGreeting/>}
