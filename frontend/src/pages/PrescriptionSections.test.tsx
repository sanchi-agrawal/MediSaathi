// @vitest-environment jsdom
import { afterEach,beforeEach,describe,expect,it,vi } from 'vitest'
import { cleanup,fireEvent,render,screen,waitFor,within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PrescriptionFlow from './PrescriptionFlow'
import type { ExtraPayload,ExtraScope,SectionClient,SectionSnapshot } from '../lib/sections'
import type { AnalysisSnapshot,PrescriptionClient } from '../lib/prescriptions'
import {schedulingClient} from '../lib/scheduling'
import type {ScheduleContext} from '../lib/scheduling'

vi.mock('../lib/image',()=>({validateImage:vi.fn(async()=>({width:4,height:4}))}))
const imageHash='a'.repeat(64)
function envelope(scope:ExtraScope):ExtraPayload {
  return scope==='instructions'?{
    schema_version:'medication-instructions-v1',source_image_sha256:imageHash,issues:[],confirmation_required:true,
    instructions:[{instruction_id:'instruction-001',medicine_name_raw:'Fictional-A',raw_text:'Fictional-A unclear instruction',
      dose_quantity_raw:null,dose_unit_raw:null,frequency_raw:null,route_raw:null,timing_raw:null,duration_raw:null,
      uncertainty_reasons:['ambiguous_dose'],needs_review:true,confirmation_required:true}],
  }:{schema_version:'prescribed-investigations-v1',source_image_sha256:imageHash,issues:[],confirmation_required:true,
    investigations:[{investigation_id:'investigation-001',test_name_raw:'Fictional test',raw_text:'Fictional test ordered',
      order_context_raw:'ordered',specimen_raw:null,variant_raw:null,timing_raw:null,
      uncertainty_reasons:['variant_unclear'],needs_review:true,confirmation_required:true}]}
}
function state(scope:ExtraScope,success=false):SectionSnapshot {
  return {analysis_id:'a',scope,revision:scope+'-r',status:success?'succeeded':'not_requested',
    payload:success?envelope(scope):null,original_payload:success?envelope(scope):null,error:null,
    reviewed:false,confirmed:false,extractor_invocations:success?1:0}
}
const medicine:AnalysisSnapshot={analysis_id:'a',revision:'m-r',status:'not_requested',records:null,original_records:null,error:null,reviewed:false,confirmed:false}
function clients(){
  const client:PrescriptionClient={current:vi.fn(async()=>null),image:vi.fn(),upload:vi.fn(async()=>medicine),analyze:vi.fn(async()=>({...medicine,status:'succeeded',records:[],original_records:[]} as AnalysisSnapshot)),
    status:vi.fn(async()=>medicine),review:vi.fn(async s=>({...s,reviewed:true})),confirm:vi.fn(async s=>({...s,confirmed:true})),
    invalidate:vi.fn(async s=>({...s,confirmed:false,reviewed:false})),explain:vi.fn(),clear:vi.fn(async()=>{})}
  const sections:SectionClient={status:vi.fn(async(_id,scope)=>state(scope)),analyze:vi.fn(async s=>state(s.scope,true)),
    invalidate:vi.fn(async s=>({...s,revision:s.revision+'-dirty',reviewed:false,confirmed:false})),
    review:vi.fn(async(s,payload)=>({...s,payload,revision:s.revision+'-saved',reviewed:true,confirmed:false})),
    confirm:vi.fn(async s=>({...s,confirmed:true}))}
  return {client,sections}
}

async function start(){
  const api=clients();render(<PrescriptionFlow {...api}/>);const user=userEvent.setup()
  expect((screen.getByRole('checkbox',{name:/Dosage instructions/}) as HTMLInputElement).checked).toBe(true)
  expect(screen.queryByText('Prescribed investigations')).toBeNull()
  expect(screen.queryByText('Strip expiry')).toBeNull()
  await user.upload(screen.getByLabelText('Upload Prescription image'),new File(['fictional'],'fictional.png',{type:'image/png'}))
  await screen.findByAltText('Prescription image selected for your review')
  return {...api,user}
}
beforeEach(()=>{URL.createObjectURL=vi.fn(()=>'blob:fictional');URL.revokeObjectURL=vi.fn()})
it('reloads association readiness after instruction confirmation even when the revision stays the same',async()=>{
 const api=clients();const instruction={...state('instructions',true),reviewed:true,confirmed:false}
 vi.mocked(api.client.current).mockResolvedValue({...medicine,status:'succeeded',records:[],original_records:[],reviewed:true,confirmed:true,sections:{instructions:instruction}})
 const context:ScheduleContext={analysis_id:'a',medicine_revision:'m-r',instruction_revision:instruction.revision,scheduling_revision:'s',ready:false,status:'blocked',medicines:[],instructions:[],instruction_issues:[],association:null,plan:null,result:null,error:null,instruction_state:{status:'succeeded',reviewed:true,confirmed:false}}
 const current=vi.spyOn(schedulingClient,'current').mockResolvedValue(context)
 render(<PrescriptionFlow {...api}/>);await screen.findByText('Save and confirm the extracted dosage instructions before preparing links.')
 current.mockResolvedValue({...context,ready:true,status:'ready',instruction_state:{status:'succeeded',reviewed:true,confirmed:true}})
 const panel=within(screen.getByRole('region',{name:'Dosage instructions review'}));const user=userEvent.setup()
 await user.click(panel.getByRole('checkbox'));await user.click(panel.getByRole('button',{name:'Confirm dosage instructions'}))
 await screen.findByText('Choose or correct a medicine–instruction link');expect(current).toHaveBeenCalledTimes(2)
 expect(vi.mocked(api.sections.confirm).mock.calls[0][0].revision).toBe(instruction.revision)
})
afterEach(()=>{cleanup();vi.restoreAllMocks()})
describe('medicine and instruction extraction only',()=>{
 it('extracts selected instructions explicitly, with no investigation or strip UI',async()=>{
  const {user,client,sections}=await start();expect(sections.analyze).not.toHaveBeenCalled()
  await user.click(screen.getByRole('checkbox',{name:/^Medicines/}));await user.click(screen.getByRole('button',{name:'Analyze Prescription with AI'}))
  await screen.findByRole('region',{name:'Dosage instructions review'})
  expect(client.analyze).not.toHaveBeenCalled();expect(sections.analyze).toHaveBeenCalledTimes(1)
  expect(vi.mocked(sections.analyze).mock.calls[0][0].scope).toBe('instructions')
  expect(screen.queryByRole('region',{name:'Prescribed investigations review'})).toBeNull()
 })
 it('saves and confirms instructions independently and invalidates edits',async()=>{
  const {user,client,sections}=await start();await user.click(screen.getByRole('button',{name:'Analyze Prescription with AI'}))
  const panel=within(await screen.findByRole('region',{name:'Dosage instructions review'}))
  await user.click(panel.getByRole('button',{name:'Save dosage instructions review'}));await waitFor(()=>expect((panel.getByRole('checkbox') as HTMLInputElement).disabled).toBe(false))
  await user.click(panel.getByRole('checkbox'));await user.click(panel.getByRole('button',{name:'Confirm dosage instructions'}));await panel.findByRole('button',{name:'Confirmed by server'})
  expect(client.confirm).not.toHaveBeenCalled()
  fireEvent.change(panel.getByLabelText('Dosage instructions: Medicine name as written 1'),{target:{value:'Corrected fictional name'}})
  await waitFor(()=>expect(sections.invalidate).toHaveBeenCalledTimes(1));expect(panel.queryByRole('button',{name:'Confirmed by server'})).toBeNull()
 })
 it('keeps successful medicines after instruction failure and retries only instructions',async()=>{
  const {user,client,sections}=await start();sections.analyze=vi.fn(async s=>({...state(s.scope),status:'failed' as const,error:{category:'network_error',message:'Offline failure'}}))
  await user.click(screen.getByRole('button',{name:'Analyze Prescription with AI'}));await screen.findByText('Dosage instructions extraction failed.')
  expect(screen.getByText(/Partial results: completed sections/)).toBeTruthy();const count=vi.mocked(client.analyze).mock.calls.length
  sections.analyze=vi.fn(async s=>state(s.scope,true));await user.click(screen.getByRole('button',{name:'Retry dosage instructions'}))
  await waitFor(()=>expect(sections.analyze).toHaveBeenCalledTimes(1));expect(client.analyze).toHaveBeenCalledTimes(count)
 })
 it('does not expose restored investigation records or their failures',async()=>{
  const api=clients();vi.mocked(api.client.current).mockResolvedValue({...medicine,sections:{instructions:state('instructions',true),investigations:{...state('investigations'),status:'failed',error:{category:'api_error',message:'Hidden legacy failure'}}}})
  render(<PrescriptionFlow {...api}/>);await screen.findByRole('region',{name:'Dosage instructions review'})
  expect(screen.queryByText('Prescribed investigations')).toBeNull();expect(screen.queryByText(/Hidden legacy failure/)).toBeNull();expect(api.sections.analyze).not.toHaveBeenCalled()
 })
})
