// @vitest-environment jsdom
import { StrictMode } from 'react'
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { render,screen,fireEvent,waitFor,cleanup,act } from '@testing-library/react'
import { MemoryRouter,Routes,Route } from 'react-router-dom'
import Review from './UnifiedPrescriptionReview'
import Schedule from './UnifiedSchedule'
import { prescriptionClient } from '../lib/prescriptions'
import type { AnalysisSnapshot } from '../lib/prescriptions'
import { sectionClient } from '../lib/sections'
import { confirmedClient } from '../lib/confirmedPrescription'
import type { WholeReview,ConfirmedPrescription,Course } from '../lib/confirmedPrescription'
import { setLanguage } from '../lib/language'
import { setTheme } from '../lib/theme'
import { invalidateSchedulingView } from '../lib/workflowEvents'
import { recognitionClient } from '../lib/recognition'
vi.mock('../components/ImageUploader',()=>({default:({onChange}:{onChange:(f:File)=>void})=><button onClick={()=>onChange(new File(['synthetic'],'test.png',{type:'image/png'}))}>Choose synthetic image</button>}))
vi.mock('../components/MedicineMatching',()=>({default:()=>null}))

const names=['Dolo','Cetirizine','Omeprazole'],durations=[5,3,7]
const records=names.map((name,index)=>({raw_text:`SYNTHETIC ${name}`,name,salt:null,strength:null,form:index===2?'capsule' as const:'tablet' as const,frequency_pattern:index===0?'1-0-1':'0-0-1',duration_days:durations[index],timing:'After food',confidence:.9,needs_review:false}))
const instructions={schema_version:'medication-instructions-v1' as const,source_image_sha256:'a'.repeat(64),issues:[],confirmation_required:true as const,instructions:records.map((m,index)=>({instruction_id:`instruction_${index}`,medicine_name_raw:m.name,raw_text:m.raw_text,dose_quantity_raw:'1',dose_unit_raw:m.form,frequency_raw:m.frequency_pattern,timing_raw:m.timing,route_raw:null,duration_raw:`${durations[index]} days`,uncertainty_reasons:[],needs_review:false,confirmation_required:true as const}))}
const pairs=names.map((_,index)=>({medicine_ref:`medicine_00${index+1}`,instruction_id:`instruction_${index}`,slots:index===0?['morning','night'] as const:index===1?['night'] as const:['morning'] as const})).map(p=>({...p,slots:[...p.slots]}))
const snapshot:ConfirmedPrescription={snapshot_id:'confirmed',analysis_id:'a',medicine_revision:'m2',instruction_revision:'i2',confirmed:true,medicines:records.map((m,index)=>({medicine_ref:pairs[index].medicine_ref,name:m.name,dose_quantity:'1',dose_unit:m.form,duration:`${durations[index]} days`,food_timing:m.timing,original_text:m.raw_text,confirmed_slots:pairs[index].slots,issues:[],review_path:`/dashboard/analysis#medicine-${index}`}))}
const source:AnalysisSnapshot={analysis_id:'a',revision:'m',records,original_records:records,status:'succeeded',reviewed:false,confirmed:false,error:null}
const whole:WholeReview={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',records,instructions,pairs,snapshot:null,medicine_status:'succeeded',instruction_status:'succeeded',recognition_mode:'gemini',review_requirements:records.map((_,index)=>({record_index:index,can_resolve:false,missing_fields:[],unsupported_fields:[],confidence_state:'acceptable'}))}
const course:Course={snapshot_id:'confirmed',start_date:'2026-11-05',blocked:[],results:records.map((m,index)=>({medicine_ref:pairs[index].medicine_ref,slots:pairs[index].slots,result:{name:m.name,start_date:'2026-11-05',end_date:['2026-11-09','2026-11-07','2026-11-11'][index],duration_days:durations[index],unit:m.form,doses_by_slot:{morning:index!==1?1:0,noon:0,night:index!==2?1:0,bedtime:0},units_per_day:index===0?2:1,total_units:durations[index]*(index===0?2:1),refill_date:null}}))}
let saved=false
beforeEach(()=>{
 saved=false
 vi.spyOn(recognitionClient,'capabilities').mockResolvedValue({mode:'gemini',ui_language_affects_extraction:false,handwriting:'experimental',accuracy_evaluated:false,script_detection_stage:'after_extraction'})
 vi.spyOn(prescriptionClient,'current').mockImplementation(async()=>({...source,revision:saved?'m2':'m',confirmed:saved}))
 vi.spyOn(prescriptionClient,'image').mockResolvedValue(new File(['synthetic'],'test.png',{type:'image/png'}))
 vi.spyOn(prescriptionClient,'upload').mockResolvedValue(source);vi.spyOn(prescriptionClient,'analyze').mockResolvedValue(source)
 vi.spyOn(prescriptionClient,'invalidate').mockResolvedValue({...source,revision:'dirty'})
 vi.spyOn(prescriptionClient,'clear').mockResolvedValue()
 vi.spyOn(sectionClient,'status').mockResolvedValue({analysis_id:'a',revision:'i',scope:'instructions',status:'not_requested',original_payload:null,payload:null,error:null,reviewed:false,confirmed:false,extractor_invocations:0})
 vi.spyOn(sectionClient,'analyze').mockResolvedValue({analysis_id:'a',revision:'i',scope:'instructions',status:'succeeded',original_payload:instructions,payload:instructions,error:null,reviewed:false,confirmed:false,extractor_invocations:1})
 vi.spyOn(confirmedClient,'review').mockImplementation(async()=>structuredClone({...whole,snapshot:saved?snapshot:null}))
 vi.spyOn(confirmedClient,'confirm').mockImplementation(async()=>{saved=true;return structuredClone(snapshot)})
 vi.spyOn(confirmedClient,'current').mockImplementation(async()=>({snapshot:saved?structuredClone(snapshot):null,course:null}))
 vi.spyOn(confirmedClient,'generate').mockResolvedValue(structuredClone(course))
})
afterEach(()=>{cleanup();setLanguage('en');setTheme('dark');vi.restoreAllMocks()})
function routes(path='/dashboard/analysis',strict=false){const tree=<MemoryRouter initialEntries={[path]}><Routes><Route path="/dashboard/analysis" element={<Review/>}/><Route path="/dashboard/schedule" element={<Schedule/>}/></Routes></MemoryRouter>;return render(strict?<StrictMode>{tree}</StrictMode>:tree)}

it('uploads, analyzes both scopes, confirms once and generates three courses with only a date',async()=>{
 vi.mocked(prescriptionClient.current).mockResolvedValueOnce(null)
 routes();await waitFor(()=>expect(screen.getByRole('button',{name:'Restore current server state'}).hasAttribute('disabled')).toBe(false))
 fireEvent.click(screen.getByText('Choose synthetic image'));fireEvent.click(screen.getByRole('button',{name:'Analyze Prescription with AI'}))
 await screen.findByRole('heading',{name:'Dolo'});await waitFor(()=>expect(screen.getByRole('button',{name:'Confirm reviewed prescription'}).hasAttribute('disabled')).toBe(false))
 expect(prescriptionClient.analyze).toHaveBeenCalledTimes(1);expect(sectionClient.analyze).toHaveBeenCalledTimes(1)
 fireEvent.click(screen.getByRole('button',{name:'Confirm reviewed prescription'}));await screen.findByText('Prescription confirmed. Scheduling needs only your start date.')
 expect(confirmedClient.confirm).toHaveBeenCalledTimes(1)
 fireEvent.click(screen.getByRole('link',{name:'Your Medicine Schedule'}));await screen.findByRole('heading',{name:'Dolo'})
 expect(screen.queryByRole('combobox')).toBeNull();expect(screen.queryByRole('checkbox')).toBeNull();expect(screen.queryByText(/1-0-1/)).toBeNull()
 expect(document.querySelectorAll('input')).toHaveLength(1)
 fireEvent.change(screen.getByLabelText('When will you start taking your medicine?'),{target:{value:'2026-11-05'}})
 fireEvent.click(screen.getByRole('button',{name:'Generate My Schedule'}));await screen.findByRole('heading',{name:'Generated medicine calendar'})
 expect(confirmedClient.generate).toHaveBeenCalledWith('confirmed','2026-11-05');expect(screen.getAllByText(/11 Nov 2026/).length).toBeGreaterThan(0)
})
it('restores the combined review under StrictMode without rerunning OCR',async()=>{routes('/dashboard/analysis',true);await screen.findByRole('heading',{name:'Dolo'});expect(prescriptionClient.analyze).not.toHaveBeenCalled();expect(sectionClient.analyze).not.toHaveBeenCalled()})
it('does not claim confirmation succeeded after a server error',async()=>{vi.mocked(confirmedClient.confirm).mockRejectedValue(new Error('Review rejected'));routes();await screen.findByRole('heading',{name:'Dolo'});fireEvent.click(screen.getByRole('button',{name:'Confirm reviewed prescription'}));await screen.findByRole('alert');expect(screen.queryByText('Prescription confirmed. Scheduling needs only your start date.')).toBeNull()})
it('restores confirmed summaries, translates Hindi and hides invalidated calendars',async()=>{saved=true;setLanguage('hi');setTheme('light');routes('/dashboard/schedule');await screen.findByRole('heading',{name:'Dolo'});expect(screen.getByRole('heading',{name:'आपकी दवा की समय-सारणी'})).toBeDefined();expect(document.documentElement.dataset.theme).toBe('light');expect(prescriptionClient.analyze).not.toHaveBeenCalled();act(()=>setLanguage('en'));expect(screen.getByRole('heading',{name:'Your Medicine Schedule'})).toBeDefined();act(()=>invalidateSchedulingView());expect(screen.queryByRole('heading',{name:'Dolo'})).toBeNull();expect(screen.getByRole('link',{name:'Return to Prescription Review'})).toBeDefined()})
it('shows generation failures without a false calendar',async()=>{saved=true;vi.mocked(confirmedClient.generate).mockRejectedValue(new Error('Source changed'));routes('/dashboard/schedule');await screen.findByRole('heading',{name:'Dolo'});fireEvent.change(screen.getByLabelText('When will you start taking your medicine?'),{target:{value:'2026-11-05'}});fireEvent.click(screen.getByRole('button',{name:'Generate My Schedule'}));await screen.findByRole('alert');expect(screen.queryByRole('heading',{name:'Generated medicine calendar'})).toBeNull()})
it('requests source-validated instruction resolution without changing its flag in browser JSON',async()=>{
 const flagged=structuredClone(whole);flagged.instructions!.instructions[0].needs_review=true;flagged.instructions!.instructions[0].uncertainty_reasons=['missing_information']
 vi.mocked(confirmedClient.review).mockImplementation(async()=>saved?structuredClone({...whole,snapshot}):structuredClone(flagged))
 routes();await screen.findByRole('heading',{name:'Dolo'})
 fireEvent.click(screen.getByRole('checkbox',{name:/I verified this instruction’s medicine/}))
 await waitFor(()=>expect(screen.getByRole('button',{name:'Confirm reviewed prescription'}).hasAttribute('disabled')).toBe(false))
 fireEvent.click(screen.getByRole('button',{name:'Confirm reviewed prescription'}));await screen.findByText('Prescription confirmed. Scheduling needs only your start date.')
 expect(confirmedClient.confirm).toHaveBeenCalledWith(expect.objectContaining({instructions:expect.objectContaining({instructions:expect.arrayContaining([expect.objectContaining({instruction_id:'instruction_0',needs_review:true})])})}),[],['instruction_0'])
})
it('does not restore a late calendar after source invalidation',async()=>{
 saved=true;let finish!:(value:Course)=>void;vi.mocked(confirmedClient.generate).mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
 routes('/dashboard/schedule');await screen.findByRole('heading',{name:'Dolo'});fireEvent.change(screen.getByLabelText('When will you start taking your medicine?'),{target:{value:'2026-11-05'}});fireEvent.click(screen.getByRole('button',{name:'Generate My Schedule'}))
 await waitFor(()=>expect(confirmedClient.generate).toHaveBeenCalledTimes(1));act(()=>invalidateSchedulingView());await act(async()=>finish(course))
 expect(screen.queryByRole('heading',{name:'Generated medicine calendar'})).toBeNull()
})
