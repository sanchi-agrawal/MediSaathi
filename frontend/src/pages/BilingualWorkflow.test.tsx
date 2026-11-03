// @vitest-environment jsdom
import { explanationCopy } from '../lib/explanationCopy'
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { cleanup,render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link,MemoryRouter,Route,Routes } from 'react-router-dom'
import PrescriptionFlow from './PrescriptionFlow'
import Schedule from './Schedule'
import ExpiryScanner from './ExpiryScanner'
import { LocalAuth } from '../components/LocalAccounts'
import { LanguageToggle } from '../components/LanguageToggle'
import { useState } from 'react'
import SectionReview from '../components/SectionReview'
import type { ExtraPayload,ExtraScope,SectionClient,SectionSnapshot } from '../lib/sections'
import { ApiError } from '../lib/prescriptions'
import type { AnalysisSnapshot,ExplanationPayload,PrescriptionClient } from '../lib/prescriptions'
import type { ScheduleContext,SchedulingClient } from '../lib/scheduling'
import { setLanguage,translate,translateError,translateReason,translateRefill } from '../lib/language'
vi.mock('../lib/image',()=>({validateImage:vi.fn(async()=>({width:8,height:8}))}))
const record={raw_text:'Dolo 650 / Paracetamol 650 mg — 1 tablet BD for 3 days',name:'Dolo 650',salt:'Paracetamol',strength:'650 mg',form:'tablet' as const,frequency_pattern:'BD',duration_days:3,timing:'morning and night',confidence:null,needs_review:true}
const source:AnalysisSnapshot={analysis_id:'fixture',revision:'v1',status:'succeeded',original_records:[record],records:[record],error:null,reviewed:false,confirmed:false}
function api():PrescriptionClient{return {current:vi.fn(async()=>source),image:vi.fn(async()=>new File(['fixture'],'source.png',{type:'image/png'})),upload:vi.fn(),analyze:vi.fn(),status:vi.fn(),invalidate:vi.fn(),review:vi.fn(async()=>({...source,reviewed:true})),confirm:vi.fn(),explain:vi.fn(async(_s:AnalysisSnapshot,language:ExplanationPayload['language']):Promise<ExplanationPayload>=>({schema_version:'prescription-explanation-v1',status:'empty',language,records_fingerprint:'test',medicines:[],issues:[],notice:language==='hi'?'पुष्ट पाठ का सारांश':'Confirmed text summary'})),clear:vi.fn(async()=>{})}}
beforeEach(()=>{setLanguage('en');URL.createObjectURL=vi.fn(()=>'blob:fixture');URL.revokeObjectURL=vi.fn()})
afterEach(()=>{cleanup();vi.restoreAllMocks();setLanguage('en')})
it('translates every prescription step, upload guidance, field label, warnings and accessibility controls immediately',async()=>{
  const client=api();const page=render(<><LanguageToggle/><PrescriptionFlow client={client}/></>)
  await screen.findByLabelText('Medicine name 1')
  await userEvent.click(screen.getByRole('button',{name:'हिंदी'}))
  expect(screen.getByRole('heading',{name:'पर्चे का विश्लेषण'})).toBeTruthy()
  for(const text of ['अपलोड करें और विश्लेषण करें','सभी दस जानकारियों की जाँच करें','पुष्टि करें और समझें','आपका पर्चा','हस्तलिखित पाठ की पहचान अभी परीक्षण के चरण में है।'])expect(screen.getByText(text)).toBeTruthy()
  expect(screen.getByRole('heading',{name:/मूल पर्चा सुरक्षित रखें/}).textContent).toContain('हर जानकारी की जाँच करें।')
  expect(screen.getByRole('button',{name:'बड़ा करके देखें'})).toBeTruthy()
  expect(screen.getByRole('button',{name:'जाँचे गए रिकॉर्ड सहेजें'})).toBeTruthy()
  expect(screen.getByRole('button',{name:'दवाइयों की पुष्टि करें'})).toBeTruthy()
  expect(page.container.textContent).not.toContain('Review all ten fields')
  expect(page.container.textContent).not.toContain('Authentication is not connected')
  expect((screen.getByLabelText('दवा का नाम 1') as HTMLInputElement).value).toBe('Dolo 650')
  expect((screen.getByLabelText('लिखी हुई क्षमता 1') as HTMLInputElement).value).toBe('650 mg')
  expect((screen.getByLabelText('दवा का मूल पाठ 1') as HTMLTextAreaElement).value).toBe(record.raw_text)
  expect(client.analyze).not.toHaveBeenCalled();expect(client.explain).not.toHaveBeenCalled()
  await userEvent.click(screen.getAllByRole('button',{name:'English'})[0]);expect(screen.getByRole('heading',{name:'Prescription analysis'})).toBeTruthy()
})
it('keeps medicine form API values unchanged when Hindi option labels are selected',async()=>{
  setLanguage('hi');const client=api();render(<PrescriptionFlow client={client}/>);await screen.findByLabelText('दवा का रूप 1')
  const form=screen.getByLabelText('दवा का रूप 1') as HTMLSelectElement
  expect(form.value).toBe('tablet');expect(screen.getByRole('option',{name:'गोली'}).getAttribute('value')).toBe('tablet')
  await userEvent.selectOptions(form,'capsule');await userEvent.click(screen.getByRole('button',{name:'जाँचे गए रिकॉर्ड सहेजें'}))
  await waitFor(()=>expect(client.review).toHaveBeenCalledWith(source,[{...record,form:'capsule'}]))
  expect(record.raw_text).toContain('1 tablet BD')
})
it('uses the existing Hindi explanation endpoint only for confirmed data and never reruns OCR on a language switch',async()=>{
  const client=api();vi.mocked(client.current).mockResolvedValue({...source,confirmed:true,reviewed:true})
  render(<><LanguageToggle/><PrescriptionFlow client={client}/></>);await screen.findByLabelText('Medicine name 1')
  await userEvent.click(screen.getByRole('button',{name:'हिंदी'}))
  expect(client.explain).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button',{name:explanationCopy.hi.action}))
  await screen.findByText('पुष्ट पाठ का सारांश')
  expect(client.explain).toHaveBeenCalledWith(expect.objectContaining({confirmed:true}),'hi')
  expect(client.upload).not.toHaveBeenCalled();expect(client.analyze).not.toHaveBeenCalled()
})
it('preserves Hindi through route navigation and remounts while new forms and warnings use it',async()=>{
  render(<MemoryRouter><LanguageToggle/><Link to="/signup">Go signup</Link><Routes><Route path="/" element={<LocalAuth/>}/><Route path="/signup" element={<LocalAuth signup/>}/></Routes></MemoryRouter>)
  const user=userEvent.setup();await user.click(screen.getAllByRole('button',{name:'हिंदी'})[0]);expect(screen.getByLabelText('ईमेल पता')).toBeTruthy()
  await user.click(screen.getByText('Go signup'));expect(screen.getByLabelText('पूरा नाम')).toBeTruthy();expect(screen.getByLabelText('पासवर्ड की पुष्टि करें')).toBeTruthy()
  await user.click(screen.getByRole('button',{name:'खाता बनाएँ'}));expect(screen.getByRole('alert').textContent).toContain('सही ईमेल')
  expect(localStorage.getItem('medisaathi.interface-language')).toBe('hi');cleanup()
  render(<MemoryRouter><LocalAuth/></MemoryRouter>);expect(screen.getByLabelText('ईमेल पता')).toBeTruthy()
})
it('translates scheduling prerequisites and the separate expiry workflow without provider calls',async()=>{
  setLanguage('hi');const blocked:ScheduleContext={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',ready:false,status:'blocked',medicines:[],instructions:[],instruction_issues:[],association:null,plan:null,result:null,error:null};const client={current:vi.fn(async()=>blocked)} as unknown as SchedulingClient
  render(<MemoryRouter><Schedule client={client}/></MemoryRouter>);await screen.findByText('संबंध जोड़ने से पहले दवाओं और निर्देशों की अलग-अलग पुष्टि करें।')
  expect(screen.getByRole('heading',{name:'आपकी दवा की समय-सारणी'})).toBeTruthy();cleanup()
  render(<ExpiryScanner/>);expect(screen.getByRole('heading',{name:'दवा की स्ट्रिप की समाप्ति तिथि जाँचें'})).toBeTruthy();expect(screen.getByRole('button',{name:'तस्वीर अपलोड करें'})).toBeTruthy()
})
it('localizes known failures and preserves safe error codes without displaying unknown backend response text',async()=>{
  setLanguage('hi');const client=api();vi.mocked(client.current).mockRejectedValue(new ApiError('image_validation_error','Technical provider detail',422))
  render(<PrescriptionFlow client={client}/>);expect((await screen.findByRole('alert')).textContent).toContain('तस्वीर मान्य नहीं है')
  expect(screen.queryByText('Technical provider detail')).toBeNull()
  expect(translateError({category:'new_provider_error',message:'private response body'})).toContain('अनुरोध पूरा नहीं हुआ')
  expect(translateError({category:'new_provider_error',message:'private response body'})).not.toContain('private response body')
  expect(translateReason('ambiguous_dose')).toBe('खुराक अस्पष्ट है')
  expect(translate('__proto__')).toBe('__proto__')
  expect(translateRefill('Dolo 650','Dolo 650: course ends in 2 days (02 Nov 2026).')).toContain('Dolo 650: कोर्स 2 दिन')
})
it('translates independent instruction and investigation review and confirmation without filling unknowns',async()=>{
  setLanguage('hi')
  function snapshot(scope:ExtraScope):SectionSnapshot{
    const meta={source_image_sha256:'a'.repeat(64),issues:[],confirmation_required:true as const}
    const payload:ExtraPayload=scope==='instructions'?{...meta,schema_version:'medication-instructions-v1',instructions:[{instruction_id:'instruction-1',medicine_name_raw:'Dolo 650',raw_text:record.raw_text,dose_quantity_raw:null,dose_unit_raw:null,frequency_raw:'BD',route_raw:null,timing_raw:null,duration_raw:null,uncertainty_reasons:['ambiguous_dose'],needs_review:true,confirmation_required:true}]}:{...meta,schema_version:'prescribed-investigations-v1',investigations:[{investigation_id:'test-1',test_name_raw:'CBC test',raw_text:'CBC test ordered',order_context_raw:null,specimen_raw:null,variant_raw:null,timing_raw:null,uncertainty_reasons:['variant_unclear'],needs_review:true,confirmation_required:true}]}
    return {analysis_id:'a',scope,revision:'v1',status:'succeeded',original_payload:payload,payload,reviewed:false,confirmed:false,error:null,extractor_invocations:1}
  }
  const client:SectionClient={status:vi.fn(),analyze:vi.fn(),invalidate:vi.fn(),review:vi.fn(async(s:SectionSnapshot,payload:ExtraPayload)=>({...s,payload,reviewed:true})),confirm:vi.fn(async(s:SectionSnapshot)=>({...s,confirmed:true}))}
  function Panel({scope}:{scope:ExtraScope}){const [s,set]=useState(()=>snapshot(scope));return <SectionReview snapshot={s} client={client} onChange={set} onRetry={()=>{}}/>}
  render(<><Panel scope="instructions"/><Panel scope="investigations"/></>)
  expect(screen.getByRole('region',{name:'खुराक के निर्देशों की जाँच'})).toBeTruthy()
  expect(screen.getByRole('region',{name:'पर्चे पर लिखी जाँचों की समीक्षा'})).toBeTruthy()
  expect(screen.getByText(/खुराक अस्पष्ट है/)).toBeTruthy();expect(screen.getByText(/जाँच का प्रकार अस्पष्ट है/)).toBeTruthy()
  expect((screen.getByLabelText('खुराक के निर्देश: खुराक की मात्रा जैसी लिखी है 1') as HTMLInputElement).value).toBe('')
  const user=userEvent.setup();await user.click(screen.getByRole('button',{name:'खुराक के निर्देशों की जाँच सहेजें'}))
  const checks=screen.getAllByRole('checkbox');await user.click(checks[0]);await user.click(screen.getByRole('button',{name:'खुराक के निर्देशों की पुष्टि करें'}))
  await screen.findByRole('button',{name:'सर्वर ने पुष्टि स्वीकार कर ली'})
  expect((screen.getByRole('button',{name:'लिखी जाँचों की पुष्टि करें'}) as HTMLButtonElement).disabled).toBe(true)
  const saved=vi.mocked(client.review).mock.calls[0][1]
  expect(saved.schema_version).toBe('medication-instructions-v1')
  expect('instructions' in saved&&saved.instructions[0].dose_quantity_raw).toBeNull()
  expect(client.confirm).toHaveBeenCalledTimes(1)
})
it('translates saved schedule inputs and slots while preserving quantities, medicine names and approval safeguards',async()=>{
  setLanguage('hi')
  const plan={dose_quantity:1,dose_unit:'tablet' as const,duration_days:3,administrations_by_slot:{morning:1,noon:0,night:1,bedtime:0},start_date:'2026-11-01'}
  const state:ScheduleContext={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',ready:true,status:'reviewed',medicines:[record],instructions:[],instruction_issues:[],association:{association_id:'link',medicine_ref:'medicine_001',instruction_id:'instruction-1'},plan,result:null,error:null}
  const client={current:vi.fn(async()=>state),approve:vi.fn()} as unknown as SchedulingClient
  render(<MemoryRouter><Schedule client={client}/></MemoryRouter>);await screen.findByLabelText('आप अपनी दवा कब से लेना शुरू करेंगे?')
  expect(screen.queryByLabelText('खुराक की मात्रा')).toBeNull()
  expect(screen.getByText('पुष्टि किया गया निर्देश रिकॉर्ड उपलब्ध नहीं है। पहले निर्देश निकालने और उनकी पुष्टि की जाँच करें।')).toBeTruthy()
  expect(screen.queryByRole('checkbox',{name:'सुबह'})).toBeNull()
  expect((screen.getByRole('button',{name:'मेरी समय-सारणी बनाएँ'}) as HTMLButtonElement).disabled).toBe(true)
  expect(client.approve).not.toHaveBeenCalled()
})
