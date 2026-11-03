// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { act,cleanup,render,screen } from '@testing-library/react'
import { acceptDemo,clearDemo,demoClient,refreshDemo,useDemoAccess } from './demoAccess'
import type { DemoStatus } from './demoAccess'
const named:DemoStatus={mode:'demo-access',active:true,display_name:'Asha Sharma',expires_in:1800,email_verified:false,account_authentication:false}
function Profile(){const s=useDemoAccess();return <p>{s.active?s.displayName||'Unnamed':'Signed out'}</p>}
afterEach(()=>{cleanup();clearDemo();vi.restoreAllMocks()})
it('restores the name from the server after a fresh mount, and clears it on logout and expiry',async()=>{
  vi.spyOn(demoClient,'status').mockResolvedValue(named)
  render(<Profile/>);await screen.findByText('Asha Sharma')
  act(()=>clearDemo());expect(screen.getByText('Signed out')).toBeTruthy()
  await act(async()=>{await refreshDemo()});expect(screen.getByText('Asha Sharma')).toBeTruthy()
  vi.mocked(demoClient.status).mockResolvedValue({...named,active:false,display_name:null,expires_in:0})
  await act(async()=>{await refreshDemo()});expect(screen.getByText('Signed out')).toBeTruthy()
  act(()=>acceptDemo({...named,display_name:null}));expect(screen.getByText('Unnamed')).toBeTruthy()
})
it('does not restore a previous user from an in-flight status response after logout or a new login',async()=>{
  let resolve!:(s:DemoStatus)=>void
  vi.spyOn(demoClient,'status').mockImplementation(()=>new Promise(r=>{resolve=r}))
  const pending=refreshDemo();clearDemo();acceptDemo({...named,display_name:null})
  resolve(named);await pending
  vi.mocked(demoClient.status).mockResolvedValue({...named,display_name:null})
  render(<Profile/>);expect(screen.getByText('Unnamed')).toBeTruthy()
  await act(async()=>{await refreshDemo()})
  expect(screen.queryByText('Asha Sharma')).toBeNull()
})
