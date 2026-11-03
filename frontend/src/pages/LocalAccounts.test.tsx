// @vitest-environment jsdom
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { act,cleanup,render,screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter,Routes,Route } from 'react-router-dom'
import { LocalAuth,LocalAccess,LocalProfile } from '../components/LocalAccounts'
import { SessionGreeting } from '../components/Personalization'
import { createLocalClient,localClient } from '../lib/localAccounts'
import type { LocalClient,LocalUser } from '../lib/localAccounts'
import { ApiError } from '../lib/prescriptions'
import { setLanguage } from '../lib/language'
const user:LocalUser={id:'user-a',full_name:'Asha Sharma',email:'asha@example.test',expires_at:2100000000}
const state=vi.hoisted(()=>({loading:false,error:false,user:null as LocalUser|null}))
vi.mock('../lib/localAccounts',async original=>({...await original<typeof import('../lib/localAccounts')>(),useLocalAccount:()=>state,setLocalUser:(u:LocalUser|null)=>{state.user=u}}))
function client():LocalClient{return {me:vi.fn(async()=>user),signup:vi.fn(async()=>user),login:vi.fn(async()=>user),logout:vi.fn(async()=>{})}}
function start(c:LocalClient,signup=false){render(<MemoryRouter><Routes><Route path="/" element={<LocalAuth client={c} signup={signup}/>}/><Route path="/dashboard" element={<LocalAccess allowDemo><SessionGreeting/><LocalProfile/></LocalAccess>}/></Routes></MemoryRouter>)}
beforeEach(()=>{state.user=null;state.loading=false;state.error=false;setLanguage('en')})
afterEach(()=>{cleanup();vi.restoreAllMocks();setLanguage('en')})
it('signs up with name and confirmed password, clears inputs, and shows registered name and initials',async()=>{
  const c=client();start(c,true);const u=userEvent.setup()
  await u.type(screen.getByLabelText('Full Name'),'Asha Sharma');await u.type(screen.getByLabelText('Email Address'),'asha@example.test');await u.type(screen.getByLabelText('Password'),'fictional-password');await u.type(screen.getByLabelText('Confirm Password'),'fictional-password')
  const storage=vi.spyOn(Storage.prototype,'setItem')
  await u.click(screen.getByRole('button',{name:'Create Account'}))
  expect(c.signup).toHaveBeenCalledWith('Asha Sharma','asha@example.test','fictional-password')
  expect(await screen.findByText('Welcome back, Asha!')).toBeTruthy();expect(screen.getByText('AS')).toBeTruthy()
  expect(screen.getAllByText('Asha Sharma')).toHaveLength(2);expect(storage).not.toHaveBeenCalled()
  await act(async()=>{setLanguage('hi')});expect(await screen.findByText('वापसी पर स्वागत है, Asha!')).toBeTruthy()
})
it('rejects mismatched passwords and clears them without a request',async()=>{
  const c=client();start(c,true);const u=userEvent.setup()
  await u.type(screen.getByLabelText('Full Name'),'Asha Sharma');await u.type(screen.getByLabelText('Email Address'),'asha@example.test');await u.type(screen.getByLabelText('Password'),'fictional-password');await u.type(screen.getByLabelText('Confirm Password'),'different-password')
  await u.click(screen.getByRole('button',{name:'Create Account'}));expect(screen.getByRole('alert').textContent).toContain('must match')
  expect(c.signup).not.toHaveBeenCalled();expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('');expect((screen.getByLabelText('Confirm Password') as HTMLInputElement).value).toBe('')
})
it.each([['invalid_credentials','Email or password is incorrect.'],['email_exists','An account with this email already exists. Sign in instead.'],['rate_limited','Too many attempts. Please try again later.']])('shows %s without fake success',async(category,message)=>{
  const c=client();vi.mocked(c.login).mockRejectedValue(new ApiError(category,'failed',401));start(c)
  const u=userEvent.setup();await u.type(screen.getByLabelText('Email Address'),'asha@example.test');await u.type(screen.getByLabelText('Password'),'incorrect');await u.click(screen.getByRole('button',{name:'Sign In'}))
  expect((await screen.findByRole('alert')).textContent).toBe(message);expect(state.user).toBeNull()
})
it('logs in with credentials and preserves generic errors in Hindi',async()=>{
  const c=client();start(c);const u=userEvent.setup();await u.type(screen.getByLabelText('Email Address'),'asha@example.test');await u.type(screen.getByLabelText('Password'),'fictional-password');await u.click(screen.getByRole('button',{name:'Sign In'}))
  expect(c.login).toHaveBeenCalledWith('asha@example.test','fictional-password');expect(screen.getByText('Welcome back, Asha!')).toBeTruthy()
  cleanup();setLanguage('hi');start(c);await u.click(screen.getByRole('button',{name:'साइन इन'}));expect(screen.getByRole('alert').textContent).toContain('सही ईमेल')
})
it('blocks logged-out or expired visitors and clears identity after successful logout',async()=>{
  render(<MemoryRouter><Routes><Route path="/" element={<LocalAccess allowDemo><p>Private workspace</p></LocalAccess>}/><Route path="/login" element={<p>Login required</p>}/></Routes></MemoryRouter>)
  expect(screen.getByText('Login required')).toBeTruthy();expect(screen.queryByText('Private workspace')).toBeNull();cleanup()
  state.user=user;const leave=vi.fn();vi.spyOn(localClient,'logout').mockResolvedValue()
  render(<MemoryRouter><LocalProfile onSignedOut={leave}/></MemoryRouter>);await userEvent.click(screen.getByRole('button',{name:'Log Out'}));expect(state.user).toBeNull();expect(leave).toHaveBeenCalledOnce()
})
it('never clears identity on failed logout',async()=>{
  state.user=user;const leave=vi.fn();vi.spyOn(localClient,'logout').mockRejectedValue(new Error('offline'));render(<MemoryRouter><LocalProfile onSignedOut={leave}/></MemoryRouter>);await userEvent.click(screen.getByRole('button',{name:'Log Out'}));await screen.findByRole('alert');expect(state.user).toEqual(user);expect(leave).not.toHaveBeenCalled()
})
it('uses JSON local auth endpoints and cookies, and detects missing cookies or HTML proxy failures',async()=>{
  const fetcher=vi.fn(async()=>new Response(JSON.stringify({user})));const c=createLocalClient(fetcher)
  expect(await c.signup('Asha Sharma','asha@example.test','fictional-password')).toEqual(user)
  expect(fetcher).toHaveBeenNthCalledWith(1,'/api/local-auth/signup',expect.objectContaining({credentials:'include',body:JSON.stringify({full_name:'Asha Sharma',email:'asha@example.test',password:'fictional-password'})}))
  expect(fetcher).toHaveBeenNthCalledWith(2,'/api/local-auth/me',expect.objectContaining({credentials:'include'}))
  fetcher.mockImplementation(async()=>new Response(JSON.stringify({detail:{category:'session_expired'}}),{status:401}))
  await expect(c.me()).resolves.toBeNull()
  fetcher.mockImplementation(async()=>new Response('<html/>'))
  await expect(c.login('asha@example.test','fictional-password')).rejects.toMatchObject({category:'invalid_response'})
})
