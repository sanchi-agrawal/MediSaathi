// @vitest-environment jsdom
import {afterEach,it,expect,vi} from 'vitest'
import {cleanup,render,screen,act} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import App from './App'
import {setLanguage} from './lib/language'
import {setTheme} from './lib/theme'
vi.mock('./components/SessionAccess',()=>({SessionAccess:({children}:{children:React.ReactNode})=>children,SessionAuth:()=>null,SessionProfile:()=>null,SessionMode:()=>null}))
vi.mock('./pages/PrescriptionFlow',()=>({default:()=> <h1>Prescription route destination</h1>}))
vi.mock('./components/Personalization',()=>({SessionGreeting:()=> <span>Welcome</span>}))
afterEach(()=>{cleanup();setLanguage('en');setTheme('dark');vi.restoreAllMocks()})
it('routes Scheduling directly to the manual planner without prescription eligibility calls',async()=>{vi.spyOn(window,'scrollTo').mockImplementation(()=>{});const requests=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('{}',{status:401}));render(<MemoryRouter initialEntries={['/dashboard/schedule']}><App/></MemoryRouter>);await screen.findByRole('heading',{name:'Manual Medicine Planner'});expect(screen.getByLabelText('Medicine name')).toBeDefined();expect(screen.queryByText('Return to Prescription Review')).toBeNull();expect(requests.mock.calls.every(([path])=>!String(path).includes('clock-scheduling')&&!String(path).includes('/prescriptions'))).toBe(true)})
it.each(['/dashboard/lab-costs','/dashboard/lab-costs/old'])('redirects retired Lab Costs URL %s to dashboard without a navigation entry',async path=>{
 vi.spyOn(window,'scrollTo').mockImplementation(()=>{});render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>);await screen.findByRole('heading',{name:'Welcome'})
 expect(document.querySelector('a[href="/dashboard/lab-costs"]')).toBeNull();expect(screen.queryByText('Lab costs')).toBeNull()
 expect(document.querySelector('a[href="/dashboard/medicine-pricing"]')).toBeTruthy()
 act(()=>{setLanguage('hi');setTheme('light')});expect(screen.queryByText('लैब जाँच का खर्च')).toBeNull();expect(document.documentElement.dataset.theme).toBe('light')
})
it.each(['/dashboard/investigations'])('redirects obsolete %s to prescription analysis',async path=>{
 vi.spyOn(window,'scrollTo').mockImplementation(()=>{});render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>);await screen.findByRole('heading',{name:'Prescription route destination'})
 expect(document.querySelector('a[href="/dashboard/investigations"]')).toBeNull();expect(document.querySelector('a[href="/dashboard/expiry"]')).toBeNull()
})
it.each(['/dashboard/strip-expiry','/dashboard/expiry','/dashboard/expiry/old'])('opens the standalone scanner at %s',async path=>{
 vi.spyOn(window,'scrollTo').mockImplementation(()=>{});render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>);await screen.findByRole('heading',{name:'Medicine Strip Expiry Scanner'})
 expect(document.querySelector('a[href="/dashboard/strip-expiry"]')).toBeTruthy()
})
it('keeps three balanced dashboard cards and no removed navigation in either language or theme',async()=>{
 vi.spyOn(window,'scrollTo').mockImplementation(()=>{});render(<MemoryRouter initialEntries={['/dashboard']}><App/></MemoryRouter>)
 expect(document.querySelectorAll('.core-stats .stat-card')).toHaveLength(4)
 expect(screen.queryByText('Investigations')).toBeNull();expect(screen.queryByText('Expiry scanner')).toBeNull()
 act(()=>{setLanguage('hi');setTheme('light')});expect(document.documentElement.dataset.theme).toBe('light')
 expect(screen.queryByText('जाँचें')).toBeNull();expect(document.querySelector('a[href="/dashboard/investigations"]')).toBeNull();expect(document.querySelector('a[href="/dashboard/expiry"]')).toBeNull()
 expect(document.querySelector('a[href="/dashboard/schedule"]')).toBeTruthy();expect(document.querySelector('a[href="/dashboard/medicines"]')).toBeTruthy()
})
