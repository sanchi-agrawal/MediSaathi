// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { cleanup,fireEvent,render,screen,waitFor,act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Pricing from './Pricing'
import MedicineMatching from '../components/MedicineMatching'
import ReminderPreview from '../components/ReminderPreview'
import { createTeamClient,parseMatches,parsePrice } from '../lib/team'
import type { Matches,Preview,PriceResult,TeamClient } from '../lib/team'
import type { AnalysisSnapshot } from '../lib/prescriptions'
import type { ScheduleContext } from '../lib/scheduling'
const source={analysis_id:'a',revision:'m'} as AnalysisSnapshot
const candidate={candidate_id:'person2:catalogue:MED001',name:'Fictional-A',salt:null,strength:null,form:'tablet',score:90,review_reasons:['salt','strength','release_type'],identity_verified:false as const}
const matches:Matches={analysis_id:'a',revision:'m',state:'ready',records:[{medicine_ref:'medicine_001',name:'Fictional-A',state:'review_required',selected:null,candidates:[candidate],message:'Candidate only'}]}
const item={kind:'medicine' as const,item_id:'MED001',name:'Audited fictional item',pack_size:null}
const unavailable:PriceResult={state:'unavailable',item,candidates:[],quotes:[],comparisons:[],reasons:['delhi_not_confirmed'],message:'No verified Delhi price available',comparisons_enabled:false,historical:true}
const schedule={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',association:{association_id:'pair'},result:{payload:{status:'ok',doses_by_slot:{morning:1,noon:0,night:1,bedtime:0}}}} as ScheduleContext
const preview:Preview={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',association_id:'pair',state:'ready',timezone:'Asia/Kolkata',window_days:7,clock_times:{morning:'08:15',night:'20:30'},doses:[{slot:'morning',due_at:'2026-11-02T08:15:00+05:30',amount:1,unit:'tablet'}],refill_notes:[],notifications_enabled:false,notice:'Reminder Preview — Notifications not enabled.'}
function client():TeamClient{return {current:vi.fn(async()=>({...matches,state:'not_requested' as const,records:[]})),match:vi.fn(async()=>matches),select:vi.fn(async()=>({...matches,records:[{...matches.records[0],selected:candidate.candidate_id}]})),catalogue:vi.fn(async()=>[item]),price:vi.fn(async()=>unavailable),preview:vi.fn(async()=>preview)}}
afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('only identifies on explicit action and only chooses after separate selection',async()=>{
  const c=client();render(<MemoryRouter><MedicineMatching source={source} client={c}/></MemoryRouter>);const user=userEvent.setup()
  await waitFor(()=>expect(c.current).toHaveBeenCalledOnce());expect(c.match).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'Find catalogue candidates'}));await screen.findByText(/Text similarity/)
  expect(c.select).not.toHaveBeenCalled();expect(screen.getByText(/salt, strength, release_type/)).toBeTruthy()
  await user.click(screen.getByRole('button',{name:'Select this candidate'}));await screen.findByRole('button',{name:/Selected by user/})
  expect(c.select).toHaveBeenCalledWith(source,'medicine_001',candidate.candidate_id)
})
it('restores prior server selection without matching again',async()=>{
  const c=client();vi.mocked(c.current).mockResolvedValue({...matches,records:[{...matches.records[0],selected:candidate.candidate_id}]})
  render(<MemoryRouter><MedicineMatching source={source} client={c}/></MemoryRouter>);await screen.findByRole('button',{name:/Selected by user/});expect(c.match).not.toHaveBeenCalled()
})
it('shows a failed matching request without chosen candidates',async()=>{
  const c=client();vi.mocked(c.match).mockRejectedValue(new Error('Catalogue unavailable'))
  render(<MemoryRouter><MedicineMatching source={source} client={c}/></MemoryRouter>);await userEvent.click(screen.getByRole('button',{name:'Find catalogue candidates'}));await screen.findByRole('alert');expect(screen.queryByText(/Selected by user/)).toBeNull()
})
it('shows honest unavailable prices and never renders a fabricated amount',async()=>{
  const c=client();render(<Pricing kind="medicine" client={c}/>);const user=userEvent.setup();await screen.findByRole('option',{name:/Audited fictional item/})
  await user.selectOptions(screen.getByLabelText('Audited catalogue item'),'MED001');await user.click(screen.getByRole('button',{name:'Check verified availability'}));await screen.findByRole('heading',{name:'No verified Delhi price available'})
  expect(c.price).toHaveBeenCalledWith('medicine',{item_id:'MED001'});expect(screen.getByRole('button',{name:/Compare prices/}).hasAttribute('disabled')).toBe(true)
})
it('shows ambiguous lookup and errors separately and clears old lookup after edits',async()=>{
  const c=client();vi.mocked(c.price).mockResolvedValue({...unavailable,state:'ambiguous',item:null,candidates:[item],reasons:['multiple_exact_catalogue_matches']})
  render(<Pricing kind="lab" client={c}/>);const user=userEvent.setup();await user.type(screen.getByLabelText('Exact original name'),'Fictional panel');await user.click(screen.getByRole('button',{name:'Check verified availability'}));await screen.findByText('Ambiguous catalogue identity — review exact variant')
  await user.type(screen.getByLabelText('Exact original name'),' changed');expect(screen.queryByText('Ambiguous catalogue identity — review exact variant')).toBeNull()
  vi.mocked(c.price).mockRejectedValue(new Error('Dataset unavailable'));await user.click(screen.getByRole('button',{name:'Check verified availability'}));await screen.findByRole('alert');expect(screen.queryByText('No exact catalogue match')).toBeNull()
})
it('requires clock preferences without default times and clears preview when changed',async()=>{
  const c=client();render(<ReminderPreview schedule={schedule} client={c}/>);const button=screen.getByRole('button',{name:'Preview approved schedule'})
  expect(button.hasAttribute('disabled')).toBe(true);expect(c.preview).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('morning preference time'),{target:{value:'08:15'}});fireEvent.change(screen.getByLabelText('night preference time'),{target:{value:'20:30'}})
  await userEvent.click(button);await screen.findByRole('status');expect(c.preview).toHaveBeenCalledWith(schedule,{morning:'08:15',night:'20:30'})
  fireEvent.change(screen.getByLabelText('morning preference time'),{target:{value:'09:00'}});expect(screen.queryByRole('status')).toBeNull()
})
it('rejects stale preview failures without a success panel and prevents double-clicks',async()=>{
  const c=client();let reject!:(e:Error)=>void;vi.mocked(c.preview).mockImplementation(()=>new Promise((_r,j)=>{reject=j}))
  render(<ReminderPreview schedule={schedule} client={c}/>);fireEvent.change(screen.getByLabelText('morning preference time'),{target:{value:'08:15'}});fireEvent.change(screen.getByLabelText('night preference time'),{target:{value:'20:30'}})
  const b=screen.getByRole('button',{name:'Preview approved schedule'});fireEvent.click(b);fireEvent.click(b);expect(c.preview).toHaveBeenCalledOnce()
  await act(async()=>reject(new Error('Schedule changed')));await screen.findByRole('alert');expect(screen.queryByRole('status')).toBeNull()
})
it('typed transport includes credentials and bindings, rejecting cross-analysis results',async()=>{
  const fetcher=vi.fn(async()=>new Response(JSON.stringify(matches),{status:200}))
  const c=createTeamClient(fetcher);await c.match(source)
  expect(fetcher).toHaveBeenCalledWith('/api/prescriptions/a/matching',expect.objectContaining({credentials:'include',body:JSON.stringify({revision:'m'})}))
  fetcher.mockResolvedValue(new Response(JSON.stringify({...matches,analysis_id:'other'})));await expect(c.match(source)).rejects.toMatchObject({category:'stale_result'})
})
it('strict response validation refuses invented prices, trusted identity or stale previews',async()=>{
  expect(()=>parsePrice({...unavailable,quotes:[{price:123}]})).toThrow()
  expect(()=>parseMatches({...matches,records:[{...matches.records[0],candidates:[{...candidate,identity_verified:true}]}]})).toThrow()
  const c=createTeamClient(vi.fn(async()=>new Response(JSON.stringify({...preview,scheduling_revision:'old'}))))
  await expect(c.preview(schedule,{morning:'08:15',night:'20:30'})).rejects.toMatchObject({category:'invalid_response'})
})
