// In-memory notifications contain no identifiers, source text or patient data.
const EVENT='medisaathi-prescription-invalidated'
const CHANNEL='medisaathi-workflow-invalidation'
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
