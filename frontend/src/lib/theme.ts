import { useSyncExternalStore } from 'react'
export type Theme='dark'|'light'
const key='medisaathi.appearance'
const listeners=new Set<()=>void>()
let current:Theme=(()=>{try{return localStorage.getItem(key)==='light'?'light':'dark'}catch{return 'dark'}})()
function apply(){if(typeof document==='undefined')return;document.documentElement.dataset.theme=current;document.documentElement.style.colorScheme=current;document.querySelector('meta[name="theme-color"]')?.setAttribute('content',current==='light'?'#FCFAFF':'#061426')}
apply()
export function setTheme(theme:Theme){current=theme;apply();try{localStorage.setItem(key,theme)}catch{/* Non-sensitive preference only. */}listeners.forEach(f=>f())}
if(typeof window!=='undefined')window.addEventListener('storage',e=>{if(e.key===key){current=e.newValue==='light'?'light':'dark';apply();listeners.forEach(f=>f())}})
export function useTheme(){const theme=useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn)}},()=>current);return {theme,setTheme}}
