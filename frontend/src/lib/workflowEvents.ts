// In-memory notifications contain no medical identifiers, source text or patient data.
const EVENT='medisaathi-prescription-invalidated'
const CHANNEL='medisaathi-workflow-invalidation'
const CHANGED='medisaathi-scheduling-changed'
const SOURCE=typeof crypto.randomUUID==='function'?crypto.randomUUID():Math.random().toString(36)
export function notifySchedulingChanged(){
  window.dispatchEvent(new Event(CHANGED))
  try{if(typeof window.BroadcastChannel==='function'){const channel=new BroadcastChannel(CHANNEL);channel.postMessage({type:'changed',source:SOURCE});channel.close()}}catch{/* Server revisions remain authoritative. */}
}
export function subscribeSchedulingChanges(callback:()=>void){
  window.addEventListener(CHANGED,callback)
  let channel:BroadcastChannel|null=null
  try{if(typeof window.BroadcastChannel==='function'){channel=new BroadcastChannel(CHANNEL);channel.onmessage=e=>{if(e.data==='changed'||e.data?.type==='changed'&&e.data.source!==SOURCE)callback()}}}catch{/* Focus refresh remains available. */}
  return()=>{window.removeEventListener(CHANGED,callback);channel?.close()}
}
export function invalidateSchedulingView(){
  if(typeof window==='undefined')return
  window.dispatchEvent(new Event(EVENT))
  if(typeof window.BroadcastChannel==='function'){
    try{const channel=new window.BroadcastChannel(CHANNEL);channel.postMessage('invalidate');channel.close()}catch{/* Browser isolation may disable cross-tab notices; never block the server invalidation. */}
  }
}
export function subscribeSchedulingInvalidation(callback:()=>void){
  const notify=()=>callback()
  window.addEventListener(EVENT,notify)
  let channel:BroadcastChannel|null=null
  try{if(typeof window.BroadcastChannel==='function')channel=new window.BroadcastChannel(CHANNEL)}catch{/* Focus/visibility refresh and server revision gates remain authoritative. */}
  if(channel)channel.onmessage=event=>{if(event.data==='invalidate')callback()}
  return()=>{window.removeEventListener(EVENT,notify);channel?.close()}
}
