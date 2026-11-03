import AccountAuth from './AccountAuth'
export default function Auth({signup=false}:{signup?:boolean}){return <AccountAuth mode={signup?'signup':'login'}/>}
