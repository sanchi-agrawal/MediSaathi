// @vitest-environment jsdom
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { act,cleanup,render,screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter,Routes,Route } from 'react-router-dom'
import DemoSignIn from './DemoSignIn'
import { DemoAccess,DemoProfile } from '../components/SessionAccess'
import { createDemoClient,demoClient } from '../lib/demoAccess'
import type { DemoClient,DemoStatus } from '../lib/demoAccess'
import { setLanguage } from '../lib/language'
import { Greeting,initials } from '../components/Personalization'
const state=vi.hoisted(()=>({loading:false,active:false,expiresAt:0,error:false,displayName:null as string|null}))
vi.mock('../lib/demoAccess',async original=>({...await original<typeof import('../lib/demoAccess')>(),useDemoAccess:()=>state}))
const active:DemoStatus={mode:'demo-access',display_name:null,active:true,expires_in:1800,email_verified:false,account_authentication:false}
function client():DemoClient{return {signup:vi.fn(async()=>active),status:vi.fn(async()=>active),login:vi.fn(async()=>active),logout:vi.fn(async()=>{})}}
function start(c=client()){
  render(<MemoryRouter><Routes><Route path="/" element={<DemoSignIn client={c}/>}/><Route path="/dashboard" element={<p>Temporary demo dashboard</p>}/></Routes></MemoryRouter>);return c
}
it('personalizes the dashboard greeting and profile in English and Hindi, without deriving names',()=>{
  state.active=true;state.displayName='Asha Sharma'
  const page=render(<><Greeting name={state.displayName}/><DemoProfile/></>)
  expect(screen.getByText('Welcome back, Asha!')).toBeTruthy()
  expect(screen.getAllByText('Asha Sharma')).toHaveLength(2)
  expect(screen.getByText('AS')).toBeTruthy()
  act(()=>setLanguage('hi'))
  expect(screen.getByText('वापसी पर स्वागत है, Asha!')).toBeTruthy()
  page.rerender(<Greeting name={null}/>)
  expect(screen.getByText('MediSaathi में आपका स्वागत है!')).toBeTruthy()
  act(()=>setLanguage('en'))
  expect(screen.getByText('Welcome to MediSaathi!')).toBeTruthy()
  expect(initials('आशा शर्मा')).toBe('आश')
})
it('rejects missing names and mismatched confirmation, clearing both passwords before requests',async()=>{
  const c=client();render(<MemoryRouter><DemoSignIn signup client={c}/></MemoryRouter>);const u=userEvent.setup()
  await u.type(screen.getByLabelText('Email address'),'visitor@example.test')
  await u.type(screen.getByLabelText('Password'),'one');await u.type(screen.getByLabelText('Confirm Password'),'two')
  await u.click(screen.getByRole('button',{name:'Continue to demo'}))
  expect(screen.getByRole('alert').textContent).toContain('full name')
  await u.type(screen.getByLabelText('Full Name'),'Asha Sharma')
  await u.type(screen.getByLabelText('Password'),'one');await u.type(screen.getByLabelText('Confirm Password'),'two')
  await u.click(screen.getByRole('button',{name:'Continue to demo'}))
  expect(screen.getByRole('alert').textContent).toContain('must match')
  expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('')
  expect((screen.getByLabelText('Confirm Password') as HTMLInputElement).value).toBe('')
  expect(c.signup).not.toHaveBeenCalled()
})
it('sends only email and display name during demo signup and restores the server name',async()=>{
  const named={...active,display_name:'Asha Sharma'}
  const fetcher=vi.fn(async()=>new Response(JSON.stringify(named)))
  expect(await createDemoClient(fetcher).signup('visitor@example.test','Asha Sharma')).toEqual(named)
  expect(fetcher).toHaveBeenNthCalledWith(1,'/api/demo-access/signup',expect.objectContaining({body:JSON.stringify({email:'visitor@example.test',display_name:'Asha Sharma'}),credentials:'include'}))
  expect(fetcher).toHaveBeenNthCalledWith(2,'/api/demo-access/status',expect.anything())
})
beforeEach(()=>{Object.assign(state,{loading:false,active:false,expiresAt:0,error:false,displayName:null});setLanguage('en')})
afterEach(()=>{cleanup();vi.restoreAllMocks();setLanguage('en')})
it('validates fictional fields and does not create an unverified identity',async()=>{
  const c=start();const u=userEvent.setup();await u.click(screen.getByRole('button',{name:'Sign In'}));expect(screen.getByRole('alert').textContent).toContain('valid email');expect(c.login).not.toHaveBeenCalled()
  expect(screen.getByText(/not secure account authentication/)).toBeTruthy()
})
it('clears password before the request, sends only email and navigates after server success',async()=>{
  const c=client();let resolve!:(s:DemoStatus)=>void;vi.mocked(c.login).mockImplementation(()=>new Promise(r=>{resolve=r}));start(c);const u=userEvent.setup();const storage=vi.spyOn(Storage.prototype,'setItem')
  await u.type(screen.getByLabelText('Email address'),'visitor@example.test');await u.type(screen.getByLabelText('Password'),'never-retain-this');await u.click(screen.getByRole('button',{name:'Sign In'}))
  expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('');expect(c.login).toHaveBeenCalledWith('visitor@example.test');expect(storage).not.toHaveBeenCalled()
  expect(screen.queryByText('Temporary demo dashboard')).toBeNull();await act(async()=>resolve(active));await screen.findByText('Temporary demo dashboard')
})
it('shows failure and never redirects on a failed session request',async()=>{
  const c=client();vi.mocked(c.login).mockRejectedValue(new Error('offline'));start(c);const u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'visitor@example.test');await u.type(screen.getByLabelText('Password'),'fictional');await u.click(screen.getByRole('button',{name:'Sign In'}));await screen.findByRole('alert');expect(screen.queryByText('Temporary demo dashboard')).toBeNull()
})
it('preserves access on refresh while valid and redirects expired sessions',async()=>{
  state.active=true;render(<MemoryRouter><DemoAccess><p>Valid refreshed workspace</p></DemoAccess></MemoryRouter>);expect(screen.getByText('Valid refreshed workspace')).toBeTruthy();cleanup();state.active=false
  render(<MemoryRouter><Routes><Route path="/" element={<DemoAccess><p>Stale workspace</p></DemoAccess>}/><Route path="/login" element={<p>Sign in again</p>}/></Routes></MemoryRouter>);await screen.findByText('Sign in again');expect(screen.queryByText('Stale workspace')).toBeNull()
})
it('blocks the dashboard while session status is unknown or failed',()=>{
  state.error=true;render(<MemoryRouter><DemoAccess><p>Private session data</p></DemoAccess></MemoryRouter>);expect(screen.getByRole('alert')).toBeTruthy();expect(screen.queryByText('Private session data')).toBeNull()
})
it('logs out only after server success and exposes a visible logout button',async()=>{
  const leave=vi.fn();vi.spyOn(demoClient,'logout').mockResolvedValue();render(<DemoProfile onSignedOut={leave}/>);await userEvent.click(screen.getByRole('button',{name:'Log Out'}));expect(demoClient.logout).toHaveBeenCalledOnce();expect(leave).toHaveBeenCalledOnce()
})
it('does not pretend logout succeeded when the server fails',async()=>{
  const leave=vi.fn();vi.spyOn(demoClient,'logout').mockRejectedValue(new Error('offline'));render(<DemoProfile onSignedOut={leave}/>);await userEvent.click(screen.getByRole('button',{name:'Log Out'}));await screen.findByRole('alert');expect(leave).not.toHaveBeenCalled()
})
it('supports Hindi validation and logout without provider requirements',async()=>{
  setLanguage('hi');const c=start();await userEvent.click(screen.getByRole('button',{name:'साइन इन'}));expect(screen.getByRole('alert').textContent).toContain('पासवर्ड');expect(c.login).not.toHaveBeenCalled();cleanup();render(<DemoProfile/>);expect(screen.getByRole('button',{name:'लॉग आउट'})).toBeTruthy()
})
it('transport uses HttpOnly-session fetches, never transmits passwords, and verifies cookie restoration',async()=>{
  const fetcher=vi.fn(async()=>new Response(JSON.stringify(active)));const c=createDemoClient(fetcher);expect(await c.login('visitor@example.test')).toEqual(active)
  expect(fetcher).toHaveBeenNthCalledWith(1,'/api/demo-access/login',expect.objectContaining({credentials:'include',body:JSON.stringify({email:'visitor@example.test'})}));expect(fetcher).toHaveBeenNthCalledWith(2,'/api/demo-access/status',expect.objectContaining({credentials:'include'}))
  fetcher.mockImplementation(async()=>new Response(JSON.stringify({...active,active:false,expires_in:0})));await expect(c.login('visitor@example.test')).rejects.toMatchObject({category:'cookie_unavailable'})
})
it('duplicate submissions issue only one login action',async()=>{
  const c=client();let resolve!:(s:DemoStatus)=>void;vi.mocked(c.login).mockImplementation(()=>new Promise(r=>{resolve=r}));start(c);const u=userEvent.setup();await u.type(screen.getByLabelText('Email address'),'visitor@example.test');await u.type(screen.getByLabelText('Password'),'fictional');await u.dblClick(screen.getByRole('button',{name:'Sign In'}));expect(c.login).toHaveBeenCalledOnce();await act(async()=>resolve(active))
})
it('shares the supplied image across sign in and demo sign up without creating an account',async()=>{
  const c=client();const first=render(<MemoryRouter><DemoSignIn client={c}/></MemoryRouter>)
  const image=first.container.querySelector('.auth-image-panel img') as HTMLImageElement
  expect(image).toBeTruthy();const source=image.getAttribute('src')
  expect(first.container.querySelector('.auth-story')).toBeNull()
  expect(screen.getByRole('link',{name:'Sign Up'}).getAttribute('href')).toBe('/signup')
  cleanup()
  const second=render(<MemoryRouter><Routes><Route path="/" element={<DemoSignIn signup client={c}/>}/><Route path="/dashboard" element={<p>Temporary demo dashboard</p>}/></Routes></MemoryRouter>)
  expect(second.container.querySelector('.auth-image-panel img')?.getAttribute('src')).toBe(source)
  expect(screen.getByText('This does not create an account.')).toBeTruthy()
  const u=userEvent.setup();await u.type(screen.getByLabelText('Full Name'),'Asha Sharma');await u.type(screen.getByLabelText('Confirm Password'),'temporary-demo');await u.type(screen.getByLabelText('Email address'),'visitor@example.test');await u.type(screen.getByLabelText('Password'),'temporary-demo');await u.click(screen.getByRole('button',{name:'Continue to demo'}))
  await screen.findByText('Temporary demo dashboard');expect(c.signup).toHaveBeenCalledWith('visitor@example.test','Asha Sharma');expect(c.login).not.toHaveBeenCalled()
})
it('translates the HTML image overlay without changing the illustration or session',async()=>{
  const c=client();const page=render(<MemoryRouter><DemoSignIn client={c}/></MemoryRouter>)
  const source=page.container.querySelector('.auth-image-panel img')?.getAttribute('src')
  expect(screen.getByRole('heading',{level:1,name:'A clearer way to manage care.'})).toBeTruthy()
  expect(screen.getByText(/Understand prescriptions/)).toBeTruthy()
  await userEvent.click(screen.getByRole('button',{name:'हिंदी'}))
  expect(screen.getByRole('heading',{level:1,name:'अपनी सेहत को बेहतर समझें।'})).toBeTruthy()
  expect(screen.getByText(/आसानी और भरोसे के साथ समझें/)).toBeTruthy()
  expect(page.container.querySelector('.auth-image-panel img')?.getAttribute('src')).toBe(source)
  expect(c.login).not.toHaveBeenCalled()
})
