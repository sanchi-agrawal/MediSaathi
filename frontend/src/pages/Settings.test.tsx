// @vitest-environment jsdom
import { beforeEach,afterEach,it,expect,vi } from 'vitest'
import { cleanup,render,screen,within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter,Routes,Route } from 'react-router-dom'
import Settings from './Settings'
import { LocalAuth } from '../components/LocalAccounts'
import { ApiError } from '../lib/prescriptions'
import type { LocalUser,LocalSettingsClient,LocalClient } from '../lib/localAccounts'
import { setLanguage } from '../lib/language'
import { setTheme } from '../lib/theme'
import { validNewPassword } from '../lib/passwordPolicy'
import { createLocalClient } from '../lib/localAccounts'
const account=vi.hoisted(()=>({loading:false,error:false,user:{id:'a',full_name:'Asha Sharma',email:'asha@example.test',expires_at:2100000000,created_at:1793491200} as LocalUser|null}))
vi.mock('../lib/localAccounts',async original=>({...await original<typeof import('../lib/localAccounts')>(),useLocalAccount:()=>account,setLocalUser:(user:LocalUser|null)=>{account.user=user},announceLocalChange:vi.fn()}))
function client():LocalSettingsClient{return {updateName:vi.fn(async full_name=>({...account.user!,full_name})),changePassword:vi.fn(async()=>({password_changed:true,signed_out:true})),deleteAccount:vi.fn(async()=>({account_deleted:true,signed_out:true,medical_archives_deleted:false})),clearWorkspace:vi.fn(async()=>({workspace_cleared:true})),logout:vi.fn(async()=>{})}}
function start(c=client()){
  render(<MemoryRouter initialEntries={['/settings']}><Routes><Route path="/settings" element={<Settings client={c}/>}/><Route path="/login" element={<p>Signed out</p>}/><Route path="/signup" element={<p>Account removed</p>}/></Routes></MemoryRouter>);return c
}
beforeEach(()=>{account.user={id:'a',full_name:'Asha Sharma',email:'asha@example.test',expires_at:2100000000,created_at:1793491200};setLanguage('en');setTheme('dark');Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','')}})})
afterEach(()=>{cleanup();vi.restoreAllMocks();setLanguage('en');setTheme('dark')})
it('renders all settings sections and updates only the display name',async()=>{
  const c=start();for(const name of ['Profile','Appearance','Language','Account & Security','Privacy & Data','Danger Zone'])expect(screen.getByRole('heading',{name})).toBeTruthy()
  expect(screen.getByText('asha@example.test')).toBeTruthy();const u=userEvent.setup();await u.clear(screen.getByLabelText('Full Name'));await u.type(screen.getByLabelText('Full Name'),'Asha Updated');await u.click(screen.getByRole('button',{name:'Save profile'}))
  await screen.findByText('Profile updated.');expect(c.updateName).toHaveBeenCalledWith('Asha Updated');expect(account.user?.id).toBe('a');expect(account.user?.email).toBe('asha@example.test')
})
it('switches global appearance and language with persisted non-sensitive preferences',async()=>{
  start();const u=userEvent.setup();await u.click(screen.getByRole('button',{name:/Light mode/}));expect(document.documentElement.dataset.theme).toBe('light');expect(localStorage.getItem('medisaathi.appearance')).toBe('light')
  await u.click(screen.getByRole('button',{name:'हिंदी'}));expect(screen.getByRole('heading',{name:'खाता और सुरक्षा'})).toBeTruthy();expect(screen.getByRole('heading',{name:'निजता और डेटा'})).toBeTruthy();expect(screen.getByRole('button',{name:'खाता हटाएँ'})).toBeTruthy()
  await u.click(screen.getByRole('button',{name:/डार्क मोड/}));expect(document.documentElement.dataset.theme).toBe('dark')
})
it('requires consent to clear a workspace and does not log out or delete the account',async()=>{
  const c=start();const u=userEvent.setup();expect((screen.getByRole('button',{name:'Clear temporary workspace'}) as HTMLButtonElement).disabled).toBe(true)
  await u.click(screen.getByRole('checkbox',{name:/Clear my current temporary/}));await u.click(screen.getByRole('button',{name:'Clear temporary workspace'}));await screen.findByText('Temporary workspace cleared. Your account is unchanged.')
  expect(c.clearWorkspace).toHaveBeenCalledOnce();expect(c.logout).not.toHaveBeenCalled();expect(c.deleteAccount).not.toHaveBeenCalled();expect(account.user?.id).toBe('a')
})
it('changes a six-character password with current verification and clears fields before awaiting',async()=>{
  const c=start();const u=userEvent.setup();await u.type(screen.getByLabelText('Current password'),'old-strong-password');await u.type(screen.getByLabelText('New password'),'new123');await u.type(screen.getByLabelText('Confirm Password'),'new123');await u.click(screen.getByRole('button',{name:'Change password'}));await screen.findByText('Signed out')
  expect(c.changePassword).toHaveBeenCalledWith('old-strong-password','new123');expect(account.user).toBeNull()
})
it('rejects five-character and mismatched new passwords without an API request',async()=>{
  const c=start();const u=userEvent.setup();await u.type(screen.getByLabelText('Current password'),'old');await u.type(screen.getByLabelText('New password'),'short');await u.type(screen.getByLabelText('Confirm Password'),'short');await u.click(screen.getByRole('button',{name:'Change password'}));expect(screen.getByRole('alert').textContent).toContain('at least 6');expect(c.changePassword).not.toHaveBeenCalled()
  expect((screen.getByLabelText('New password') as HTMLInputElement).value).toBe('')
})
it('deletes only after password and explicit consent, then clears identity and redirects',async()=>{
  const c=start();const u=userEvent.setup();await u.click(screen.getByRole('button',{name:'Delete Account'}));const modal=within(screen.getByRole('dialog'))
  expect(modal.getByText(/does not erase external archives/)).toBeTruthy();expect((modal.getByRole('button',{name:'Permanently delete account'}) as HTMLButtonElement).disabled).toBe(true);expect(c.deleteAccount).not.toHaveBeenCalled()
  await u.type(modal.getByLabelText('Current password'),'correct-password');await u.click(modal.getByRole('checkbox'));await u.click(modal.getByRole('button',{name:'Permanently delete account'}));await screen.findByText('Account removed')
  expect(c.deleteAccount).toHaveBeenCalledWith('correct-password',true);expect(account.user).toBeNull()
})
it('keeps an account and dialog open after incorrect password or database failures',async()=>{
  const c=client();vi.mocked(c.deleteAccount).mockRejectedValue(new ApiError('current_password_incorrect','failed',403));start(c);const u=userEvent.setup();await u.click(screen.getByRole('button',{name:'Delete Account'}));const modal=within(screen.getByRole('dialog'))
  await u.type(modal.getByLabelText('Current password'),'wrong');await u.click(modal.getByRole('checkbox'));await u.click(modal.getByRole('button',{name:'Permanently delete account'}));expect((await modal.findByRole('alert')).textContent).toContain('Current password is incorrect');expect(account.user?.id).toBe('a');expect((modal.getByLabelText('Current password') as HTMLInputElement).value).toBe('')
  vi.mocked(c.deleteAccount).mockRejectedValue(new ApiError('storage_unavailable','failed',503));await u.type(modal.getByLabelText('Current password'),'correct-password');await u.click(modal.getByRole('button',{name:'Permanently delete account'}));await modal.findByRole('alert');expect(screen.queryByText('Account removed')).toBeNull()
})
it.each([[5,false],[6,true],[7,true],[8,true],[128,true],[129,false]])('new password length %s has validity %s',(size,valid)=>{expect(validNewPassword('x'.repeat(Number(size)))).toBe(valid)})
it.each([['short',false],['six123',true],['a secure longer passphrase',true]])('signup policy accepts %s only when valid',async(password,valid)=>{
  const c:LocalClient={me:vi.fn(),login:vi.fn(),signup:vi.fn(async()=>account.user!),logout:vi.fn()};render(<MemoryRouter><Routes><Route path="/" element={<LocalAuth signup client={c}/>}/><Route path="/dashboard" element={<p>Registered</p>}/></Routes></MemoryRouter>);const u=userEvent.setup();await u.type(screen.getByLabelText('Full Name'),'Asha Sharma');await u.type(screen.getByLabelText('Email Address'),'asha@example.test');await u.type(screen.getByLabelText('Password'),String(password));await u.type(screen.getByLabelText('Confirm Password'),String(password));await u.click(screen.getByRole('button',{name:'Create Account'}))
  if(valid){await screen.findByText('Registered');expect(c.signup).toHaveBeenCalled()}else{expect(screen.getByRole('alert').textContent).toContain('at least 6');expect(c.signup).not.toHaveBeenCalled()}
})
it('uses cookie-authenticated settings requests and rejects incomplete deletion success responses',async()=>{
  const fetcher=vi.fn(async()=>new Response(JSON.stringify({account_deleted:true,signed_out:true,medical_archives_deleted:false})))
  const c=createLocalClient(fetcher);await c.deleteAccount('fictional-password',true)
  expect(fetcher).toHaveBeenCalledWith('/api/local-auth/delete-account',expect.objectContaining({method:'POST',credentials:'include',headers:expect.objectContaining({'X-MediSaathi-Action':'review'}),body:JSON.stringify({current_password:'fictional-password',confirm:true})}))
  fetcher.mockImplementation(async()=>new Response(JSON.stringify({account_deleted:true})))
  await expect(c.deleteAccount('fictional-password',true)).rejects.toMatchObject({category:'invalid_response'})
})
