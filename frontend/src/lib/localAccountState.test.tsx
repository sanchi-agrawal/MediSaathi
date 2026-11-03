// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { act,cleanup,render,screen } from '@testing-library/react'
import { localClient,setLocalUser,refreshLocal,useLocalAccount } from './localAccounts'
import type { LocalUser } from './localAccounts'
const user:LocalUser={id:'a',full_name:'Asha Sharma',email:'asha@example.test',expires_at:2100000000}
function Profile(){const s=useLocalAccount();return <p>{s.user?.full_name||'Signed out'}</p>}
afterEach(()=>{cleanup();setLocalUser(null);vi.restoreAllMocks()})
it('restores authenticated identity from me on refresh and clears expired sessions',async()=>{
  vi.spyOn(localClient,'me').mockResolvedValue(user);render(<Profile/>);await screen.findByText('Asha Sharma')
  vi.mocked(localClient.me).mockResolvedValue(null);await act(async()=>{await refreshLocal()});expect(screen.getByText('Signed out')).toBeTruthy()
})
it('does not resurrect an old account from a delayed restoration after logout or a new login',async()=>{
  let resolve!:(v:LocalUser|null)=>void;vi.spyOn(localClient,'me').mockImplementation(()=>new Promise(r=>{resolve=r}))
  const request=refreshLocal();setLocalUser(null);setLocalUser({...user,id:'b',full_name:'Ravi Kumar'});resolve(user);await request
  vi.mocked(localClient.me).mockResolvedValue({...user,id:'b',full_name:'Ravi Kumar'});render(<Profile/>);expect(screen.getByText('Ravi Kumar')).toBeTruthy();await act(async()=>{await refreshLocal()});expect(screen.queryByText('Asha Sharma')).toBeNull()
})
