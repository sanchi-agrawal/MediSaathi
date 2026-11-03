// @vitest-environment jsdom
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { act,cleanup,render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter,Route,Routes } from 'react-router-dom'
import AccountAuth from './AccountAuth'
import MyPrescriptions from './MyPrescriptions'
import { AccountAccess,AccountProfile } from '../components/AccountAccess'
import { accountClient,createAccountClient } from '../lib/accounts'
import type { AccountClient,AccountState,ArchiveView } from '../lib/accounts'
import { setLanguage } from '../lib/language'
import { ApiError } from '../lib/prescriptions'
const mocked=vi.hoisted(()=>({state:{loading:false,configured:true,storage_configured:true,user:null,error:''} as AccountState}))
vi.mock('../lib/accounts',async original=>({...await original<typeof import('../lib/accounts')>(),useAccount:()=>mocked.state}))
const profile={id:'11111111-1111-4111-8111-111111111111',email:'fictional@example.test',name:'Fictional user'}
function client():AccountClient{return {status:vi.fn(),me:vi.fn(),login:vi.fn(async()=>profile),signup:vi.fn(async()=>({next:'verify_email'})),verify:vi.fn(async()=>({verified:true})),forgot:vi.fn(async()=>({})),reset:vi.fn(async()=>({reset:true})),logout:vi.fn(async()=>({signed_out:true})),history:vi.fn(async()=>[]),save:vi.fn(),view:vi.fn(),remove:vi.fn(),resume:vi.fn()}}
function auth(mode:'login'|'signup'|'forgot'|'verify'|'reset',c=client()){
  render(<MemoryRouter><Routes><Route path="/" element={<AccountAuth mode={mode} client={c}/>}/><Route path="/dashboard" element={<p>Verified dashboard destination</p>}/></Routes></MemoryRouter>);return c
}
beforeEach(()=>{mocked.state={loading:false,configured:true,storage_configured:true,user:null,error:''};setLanguage('en')})
afterEach(()=>{cleanup();vi.restoreAllMocks();setLanguage('en')})
it('uses real login transport and redirects only after server success',async()=>{
  const c=auth('login'),u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.type(screen.getByLabelText('Password'),'fictional-password');await u.click(screen.getByRole('button',{name:'Sign In'}))
  await screen.findByText('Verified dashboard destination');expect(c.login).toHaveBeenCalledWith('fictional@example.test','fictional-password')
})
it('shows login failure without success or redirect',async()=>{
  const c=client();vi.mocked(c.login).mockRejectedValue(new ApiError('invalid_credentials','private provider text',401));auth('login',c);const u=userEvent.setup()
  await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.type(screen.getByLabelText('Password'),'wrong');await u.click(screen.getByRole('button',{name:'Sign In'}));await screen.findByRole('alert')
  expect(screen.queryByText('Verified dashboard destination')).toBeNull();expect(screen.queryByText('private provider text')).toBeNull()
})
it('signs up with provider verification instructions, never a fake logged-in session',async()=>{
  const c=auth('signup'),u=userEvent.setup();await u.type(screen.getByLabelText('Full name'),'Fictional user');await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.type(screen.getByLabelText('Password'),'fictional-password-16E');await u.click(screen.getByRole('button',{name:'Sign Up'}))
  await screen.findByText(/If eligible, check your email/);expect(c.signup).toHaveBeenCalledOnce();expect(c.login).not.toHaveBeenCalled()
})
it('supports forgot password, OTP verification and reset as separate provider actions',async()=>{
  let c=auth('forgot');let u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.click(screen.getByRole('button',{name:'Forgot Password'}));await screen.findByText(/recovery code/);expect(c.forgot).toHaveBeenCalledOnce();cleanup()
  c=auth('verify');u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.type(screen.getByLabelText('Email verification code'),'123456');await u.click(screen.getByRole('button',{name:'Verify Email'}));await screen.findByText('Email verified. You can now sign in.');cleanup()
  c=auth('reset');u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.type(screen.getByLabelText('Email verification code'),'123456');await u.type(screen.getByLabelText('Password'),'new-fictional-password');await u.click(screen.getByRole('button',{name:'Reset Password'}));await screen.findByText(/Password changed/);expect(c.reset).toHaveBeenCalledWith('fictional@example.test','123456','new-fictional-password')
})
it('shows accurate missing configuration and disables submission',()=>{
  mocked.state.configured=false;const c=auth('login');expect((screen.getByRole('button',{name:'Sign In'}) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getAllByText(/Account setup unavailable/).length).toBeGreaterThan(0);expect(screen.queryByText(/UI PREVIEW/)).toBeNull();expect(c.login).not.toHaveBeenCalled()
})
it('changes auth labels, validation, loading/error states and logout into Hindi',async()=>{
  setLanguage('hi');const c=auth('login'),u=userEvent.setup();expect(screen.getByLabelText('ईमेल पता')).toBeTruthy();await u.click(screen.getByRole('button',{name:'साइन इन'}));expect(screen.getByRole('alert').textContent).toContain('सही ईमेल')
  await u.type(screen.getByLabelText('ईमेल पता'),'fictional@example.test');await u.type(screen.getByLabelText('पासवर्ड'),'wrong');vi.mocked(c.login).mockRejectedValue(new ApiError('rate_limited','private',429));await u.click(screen.getByRole('button',{name:'साइन इन'}));await screen.findByText(/बहुत अधिक प्रयास/);cleanup()
  mocked.state.user=profile;render(<MemoryRouter><AccountProfile/></MemoryRouter>);expect(screen.getByRole('button',{name:'साइन आउट'})).toBeTruthy()
})
it('protects configured account routes and allows the clearly separate unconfigured demo',async()=>{
  render(<MemoryRouter><Routes><Route path="/" element={<AccountAccess><p>Private history</p></AccountAccess>}/><Route path="/login" element={<p>Login destination</p>}/></Routes></MemoryRouter>);await screen.findByText('Login destination');expect(screen.queryByText('Private history')).toBeNull();cleanup()
  mocked.state.configured=false;render(<MemoryRouter><AccountAccess allowDemo><p>Public demo workspace</p></AccountAccess></MemoryRouter>);expect(screen.getByText('Public demo workspace')).toBeTruthy()
})
it('transport restores sessions, sends credentials, and never returns provider tokens',async()=>{
  const fetcher=vi.fn(async()=>new Response(JSON.stringify({user:profile})));const c=createAccountClient(fetcher);expect(await c.me()).toEqual(profile);await c.login('fictional@example.test','fictional-password')
  expect(fetcher).toHaveBeenLastCalledWith('/api/auth/login',expect.objectContaining({credentials:'include',headers:expect.objectContaining({'X-MediSaathi-Action':'review'})}))
  fetcher.mockImplementation(async()=>new Response(JSON.stringify({detail:{category:'session_expired'}}),{status:401}));expect(await c.me()).toBeNull()
  await expect(c.logout()).rejects.toMatchObject({status:401})
})
it('prevents duplicate login submissions while provider work is pending',async()=>{
  const c=client();let resolve!:(u:typeof profile)=>void;vi.mocked(c.login).mockImplementation(()=>new Promise(r=>{resolve=r}));auth('login',c);const u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'fictional@example.test');await u.type(screen.getByLabelText('Password'),'fictional-password');const button=screen.getByRole('button',{name:'Sign In'});await u.dblClick(button);expect(c.login).toHaveBeenCalledOnce();await act(async()=>resolve(profile))
})
it('requires explicit save consent, displays historical data, and deletes through owner-scoped transport',async()=>{
  mocked.state.user=profile;const c=client();const meta={id:'saved',version:'v',created_at:'2026-10-31T08:00:00Z',expires_at:'2026-11-30T08:00:00Z',historical:true as const}
  const archived:ArchiveView={...meta,image_saved:true,approval_authority_restored:false,payload:{captured_at:meta.created_at,prescription:{analysis_id:'old',sections:{medicines:{payload:[{name:'Original',salt:null}],reviewed:[{name:'Reviewed',salt:null}]}}},confirmed_scopes:['medicines'],scheduling_state:{status:'succeeded'}}}
  vi.mocked(c.history).mockResolvedValue([meta]);vi.mocked(c.view).mockResolvedValue(archived);vi.mocked(c.remove).mockResolvedValue({deleted:true})
  render(<MemoryRouter><MyPrescriptions client={c}/></MemoryRouter>);await screen.findByRole('button',{name:'View / Continue Review'});expect((screen.getByRole('button',{name:'Save to my account'}) as HTMLButtonElement).disabled).toBe(true)
  await userEvent.click(screen.getByRole('button',{name:'View / Continue Review'}));await screen.findByRole('region',{name:'Historical prescription'});expect(screen.getByText(/Historical confirmed scopes/)).toBeTruthy();expect((screen.getByRole('button',{name:'Continue Review'}) as HTMLButtonElement).disabled).toBe(true)
  await userEvent.click(screen.getByRole('button',{name:'Delete saved record'}));await waitFor(()=>expect(c.remove).toHaveBeenCalledWith('saved'));expect(c.resume).not.toHaveBeenCalled()
})
it('sign-out failures do not pretend that the server session was invalidated',async()=>{
  mocked.state.user=profile;vi.spyOn(accountClient,'logout').mockRejectedValue(new ApiError('network_error','offline'))
  render(<MemoryRouter><AccountProfile/></MemoryRouter>);await userEvent.click(screen.getByRole('button',{name:'Sign Out'}));await screen.findByText('Sign out could not reach the server. Please try again.')
})
it('retranslates existing success and validation states when the user switches language',async()=>{
  const c=auth('forgot'),u=userEvent.setup();await u.click(screen.getByRole('button',{name:'Forgot Password'}))
  expect(screen.getByRole('alert').textContent).toContain('Enter a valid email')
  await act(async()=>setLanguage('hi'));expect(screen.getByRole('alert').textContent).toContain('सही ईमेल')
  await u.type(screen.getByLabelText('ईमेल पता'),'fictional@example.test');await u.click(screen.getByRole('button',{name:'पासवर्ड भूल गए'}));await screen.findByText(/रिकवरी कोड देखें/)
  await act(async()=>setLanguage('en'));expect(screen.getByText(/If eligible, check your email for a recovery code/)).toBeTruthy();expect(c.forgot).toHaveBeenCalledOnce()
})
