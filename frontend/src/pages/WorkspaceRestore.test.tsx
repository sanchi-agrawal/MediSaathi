// @vitest-environment jsdom
import { explanationCopy } from '../lib/explanationCopy'
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { act,cleanup,render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link,MemoryRouter,Route,Routes } from 'react-router-dom'
import PrescriptionFlow from './PrescriptionFlow'
import CurrentWorkspace from './CurrentWorkspace'
import Schedule from './Schedule'
import type { AnalysisSnapshot,ExplanationPayload,PrescriptionClient } from '../lib/prescriptions'
import type { SchedulingClient,ScheduleContext } from '../lib/scheduling'
import type { Language } from '../lib/api'
vi.mock('../lib/image',()=>({validateImage:vi.fn(async()=>({width:4,height:4}))}))

const medicine={raw_text:'Fictional-A 1 tablet BD morning and night for 3 days',name:'Fictional-A',salt:null,strength:'250 mg',form:'tablet' as const,frequency_pattern:'BD',duration_days:3,timing:'morning and night',confidence:null,needs_review:false}
const instruction={instruction_id:'instruction_001',medicine_name_raw:'Fictional-A',raw_text:medicine.raw_text,dose_quantity_raw:'1',dose_unit_raw:'tablet',frequency_raw:'BD',route_raw:null,timing_raw:'morning and night',duration_raw:'3 days',uncertainty_reasons:[],needs_review:false,confirmation_required:true as const}
const snapshot:AnalysisSnapshot={analysis_id:'a',revision:'m',status:'succeeded',original_records:[medicine],records:[medicine],error:null,reviewed:true,confirmed:true,
  sections:{instructions:{analysis_id:'a',scope:'instructions',revision:'i',status:'succeeded',original_payload:{schema_version:'medication-instructions-v1',source_image_sha256:'a'.repeat(64),instructions:[instruction],issues:[],confirmation_required:true},payload:{schema_version:'medication-instructions-v1',source_image_sha256:'a'.repeat(64),instructions:[instruction],issues:[],confirmation_required:true},error:null,reviewed:true,confirmed:true,extractor_invocations:1}}}
const labels:Record<Language,string>={en:'Medicine name: Fictional-A',hi:'दवा का नाम: Fictional-A',hinglish:'Dawa ka naam: Fictional-A'}
function explanation(language:Language):ExplanationPayload{return {schema_version:'prescription-explanation-v1',status:'explained',language,records_fingerprint:'fixed',medicines:[{record_index:0,fields:[{field:'name',label:'Name',text:labels[language],display_value:'Fictional-A',is_unknown:false},{field:'strength',label:'Strength',text:language==='hi'?'लिखी हुई शक्ति: 250 mg':'Written strength: 250 mg',display_value:'250 mg',is_unknown:false}],glossary:null}],issues:[],notice:language==='hi'?'केवल पुष्टि किए गए पाठ की व्याख्या':'Confirmed text only'}}
function client():PrescriptionClient{return {current:vi.fn(async()=>snapshot),image:vi.fn(async()=>new File(['fictional'],'current.png',{type:'image/png'})),upload:vi.fn(),analyze:vi.fn(),status:vi.fn(async()=>snapshot),invalidate:vi.fn(async()=>({...snapshot,reviewed:false,confirmed:false,revision:'dirty'})),review:vi.fn(),confirm:vi.fn(),explain:vi.fn(async(_s,l)=>explanation(l)),clear:vi.fn(async()=>{})}}
const scheduleState:ScheduleContext={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',ready:true,status:'succeeded',medicines:[medicine],instructions:[instruction],instruction_issues:[],association:{association_id:'link',medicine_ref:'medicine_001',instruction_id:'instruction_001'},plan:{dose_quantity:1,dose_unit:'tablet',duration_days:3,administrations_by_slot:{morning:1,noon:0,night:1,bedtime:0},start_date:'2026-10-27'},result:{derived_id:'r',payload:{name:'Fictional-A',status:'ok',reason:null,doses_by_slot:{morning:1,noon:0,night:1,bedtime:0},units_per_day:2,duration_days:3,total_units:6,unit:'tablet',start_date:'2026-10-27',end_date:'2026-10-29',refill_date:null}},error:null}
beforeEach(()=>{URL.createObjectURL=vi.fn(()=>'blob:fixture');URL.revokeObjectURL=vi.fn()})
afterEach(()=>{cleanup();vi.restoreAllMocks()})
scheduleState.course_results=[{association:scheduleState.association!,plan:scheduleState.plan!,result:scheduleState.result as NonNullable<ScheduleContext['course_results']>[number]['result']}]
it('navigates Analysis → Medicines → Schedule → Analysis with the same saved server state and no OCR',async()=>{
  const api=client();const schedules:SchedulingClient={current:vi.fn(async()=>scheduleState),associate:vi.fn(),clear:vi.fn(),invalidate:vi.fn(),review:vi.fn(),approve:vi.fn()}
  render(<MemoryRouter><nav><Link to="/">Nav analysis</Link><Link to="/medicines">Nav medicines</Link><Link to="/schedule">Nav schedule</Link></nav><Routes><Route path="/" element={<PrescriptionFlow client={api}/>}/><Route path="/medicines" element={<CurrentWorkspace kind="medicines" client={api}/>}/><Route path="/schedule" element={<Schedule client={schedules}/>}/></Routes></MemoryRouter>)
  await screen.findByLabelText('Medicine name 1');await screen.findByAltText('Prescription image selected for your review')
  const user=userEvent.setup();await user.click(screen.getByText('Nav medicines'));await screen.findByRole('heading',{name:'Fictional-A'})
  await user.click(screen.getByText('Nav schedule'));await screen.findByRole('region',{name:'Calculated schedule'})
  expect(screen.getByText(/Course total: 6 tablet/)).toBeTruthy()
  await user.click(screen.getByText('Nav analysis'));await screen.findByLabelText('Medicine name 1')
  expect((screen.getByLabelText('Medicine name 1') as HTMLInputElement).value).toBe('Fictional-A')
  expect(api.current).toHaveBeenCalledTimes(3);expect(api.image).toHaveBeenCalledWith(snapshot)
  expect(api.upload).not.toHaveBeenCalled();expect(api.analyze).not.toHaveBeenCalled();expect(api.clear).not.toHaveBeenCalled()
  expect(schedules.approve).not.toHaveBeenCalled()
})
it('Hindi and Hinglish only fetch source details after an explicit action',async()=>{
  const api=client();render(<PrescriptionFlow client={api}/>);await screen.findByLabelText('Medicine name 1');const user=userEvent.setup()
  await user.click(screen.getByRole('button',{name:'हिन्दी'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hi');await user.click(screen.getByRole('button',{name:explanationCopy.hi.action}));await screen.findByText(labels.hi)
  expect(api.explain).toHaveBeenLastCalledWith(snapshot,'hi');expect(screen.getByText('लिखी हुई शक्ति: 250 mg')).toBeTruthy()
  expect(screen.getByRole('region',{name:'Confirmed medicine explanation'}).getAttribute('aria-label')).toBeTruthy()
  expect((screen.getByLabelText('Original medicine text 1') as HTMLTextAreaElement).value).toBe(medicine.raw_text)
  await user.click(screen.getByRole('button',{name:'Hinglish'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hinglish');await user.click(screen.getByRole('button',{name:explanationCopy.hinglish.action}));await screen.findByText(labels.hinglish)
  await user.click(screen.getByRole('button',{name:'English'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'en');await user.click(screen.getByRole('button',{name:explanationCopy.en.action}));await screen.findByText(labels.en)
  expect(api.analyze).not.toHaveBeenCalled()
})
it('shows Hindi prerequisites without calling explanation for unconfirmed medicines',async()=>{
  const api=client();vi.mocked(api.current).mockResolvedValue({...snapshot,confirmed:false})
  render(<PrescriptionFlow client={api}/>);await screen.findByLabelText('Medicine name 1');await userEvent.click(screen.getByRole('button',{name:'हिन्दी'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hi');await userEvent.click(screen.getByRole('button',{name:explanationCopy.hi.action}))
  expect(screen.getByText(/चुनी हुई भाषा के लिए पहले/)).toBeTruthy();expect(api.explain).not.toHaveBeenCalled()
  expect(screen.queryByRole('region',{name:'Confirmed medicine explanation'})).toBeNull()
})
it('never restores a late old analysis over a newly selected image',async()=>{
  const api=client();let resolve!:(s:AnalysisSnapshot)=>void;vi.mocked(api.current).mockImplementation(()=>new Promise(r=>{resolve=r}))
  render(<PrescriptionFlow client={api}/>);await userEvent.upload(screen.getByLabelText('Upload Prescription image'),new File(['new'],'new.png',{type:'image/png'}));await screen.findByAltText('Prescription image selected for your review')
  await act(async()=>resolve(snapshot));expect(screen.queryByLabelText('Medicine name 1')).toBeNull();expect(api.image).not.toHaveBeenCalled()
})
it('surfaces explanation errors without stale-language success',async()=>{
  const api=client();vi.mocked(api.explain).mockRejectedValue(new Error('Unavailable'))
  render(<PrescriptionFlow client={api}/>);await screen.findByLabelText('Medicine name 1');await userEvent.click(screen.getByRole('button',{name:'हिन्दी'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hi');await userEvent.click(screen.getByRole('button',{name:explanationCopy.hi.action}))
  await screen.findAllByRole('alert');expect(screen.queryByRole('region',{name:'Confirmed medicine explanation'})).toBeNull()
})
it('discards stale-language responses after source replacement',async()=>{
  const api=client();let resolve!:(s:ExplanationPayload)=>void;vi.mocked(api.explain).mockImplementation(()=>new Promise(r=>{resolve=r}))
  render(<PrescriptionFlow client={api}/>);await screen.findByAltText('Prescription image selected for your review');await userEvent.click(screen.getByRole('button',{name:'हिन्दी'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hi');await userEvent.click(screen.getByRole('button',{name:explanationCopy.hi.action}));await waitFor(()=>expect(api.explain).toHaveBeenCalledTimes(1))
  await userEvent.click(screen.getByRole('button',{name:'Remove image'}));await act(async()=>resolve(explanation('hi')))
  expect(screen.queryByRole('region',{name:'Confirmed medicine explanation'})).toBeNull();expect(api.clear).toHaveBeenCalledTimes(1)
})
it('shows confirmed instruction values with Hindi descriptions and excludes unconfirmed test facts',async()=>{
  const api=client();vi.mocked(api.explain).mockResolvedValue({...explanation('hi'),summary:{schema_version:'confirmed-prescription-summary-v1',language:'hi',title:'पुष्टि किए गए पर्चे का सारांश',notice:'केवल पुष्टि किया गया पाठ',medicine_count:1,sections:{instructions:{title:'पुष्टि किए गए खुराक निर्देश',confirmed:true,issues:[],records:[{record_id:'instruction_001',original_text:medicine.raw_text,fields:[{field:'dose_quantity_raw',label:'खुराक की मात्रा',value:'1',is_unknown:false,text:'खुराक की मात्रा: 1'},{field:'dose_unit_raw',label:'खुराक की इकाई',value:'tablet',is_unknown:false,text:'खुराक की इकाई: tablet'}],uncertainty_reasons:[],needs_review:false}]},investigations:{title:'पुष्टि की गई जाँचें',confirmed:false,issues:[],records:[]}}}})
  render(<PrescriptionFlow client={api}/>);await screen.findByLabelText('Medicine name 1');await userEvent.click(screen.getByRole('button',{name:'हिन्दी'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hi');await userEvent.click(screen.getByRole('button',{name:explanationCopy.hi.action}))
  await screen.findByText('खुराक की मात्रा: 1');expect(screen.getByText('खुराक की इकाई: tablet')).toBeTruthy()
  expect(screen.queryByRole('heading',{name:'पुष्टि की गई जाँचें'})).toBeNull()
  expect(screen.queryByText(/इस अनुभाग की पुष्टि नहीं हुई/)).toBeNull()
  expect((screen.getByLabelText('Original medicine text 1') as HTMLTextAreaElement).value).toBe(medicine.raw_text)
})
it('removes stale records, confirmation, explanation and preview when explicit restoration finds an expired session',async()=>{
  const api=client();render(<PrescriptionFlow client={api}/>);await screen.findByAltText('Prescription image selected for your review')
  const user=userEvent.setup();await user.click(screen.getByRole('button',{name:'हिन्दी'}));expect(api.explain).not.toHaveBeenCalledWith(snapshot,'hi');await user.click(screen.getByRole('button',{name:explanationCopy.hi.action}));await screen.findByText(labels.hi)
  vi.mocked(api.current).mockResolvedValue(null)
  await user.click(screen.getByRole('button',{name:'Restore current session'}))
  await waitFor(()=>expect(screen.queryByLabelText('Medicine name 1')).toBeNull())
  expect(screen.queryByRole('region',{name:'Confirmed medicine explanation'})).toBeNull()
  expect(screen.queryByAltText('Prescription image selected for your review')).toBeNull()
  expect(screen.queryByRole('button',{name:'Confirmed by server'})).toBeNull()
  expect(api.clear).not.toHaveBeenCalled();expect(api.upload).not.toHaveBeenCalled();expect(api.analyze).not.toHaveBeenCalled()
})
