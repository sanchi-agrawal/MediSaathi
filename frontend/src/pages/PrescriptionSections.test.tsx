// @vitest-environment jsdom
import { afterEach,beforeEach,describe,expect,it,vi } from 'vitest'
import { cleanup,fireEvent,render,screen,waitFor,within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PrescriptionFlow from './PrescriptionFlow'
import type { ExtraPayload,ExtraScope,SectionClient,SectionSnapshot } from '../lib/sections'
import type { AnalysisSnapshot,PrescriptionClient } from '../lib/prescriptions'

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
  const client:PrescriptionClient={upload:vi.fn(async()=>medicine),analyze:vi.fn(async()=>({...medicine,status:'succeeded',records:[],original_records:[]} as AnalysisSnapshot)),
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
  await user.click(screen.getByRole('checkbox',{name:/Dosage instructions/}))
  await user.click(screen.getByRole('checkbox',{name:/Prescribed investigations/}))
  await user.upload(screen.getByLabelText('Upload Prescription image'),new File(['fictional'],'fictional.png',{type:'image/png'}))
  await screen.findByAltText('Prescription image selected for your review')
  return {...api,user}
}
beforeEach(()=>{URL.createObjectURL=vi.fn(()=>'blob:fictional');URL.revokeObjectURL=vi.fn()})
afterEach(()=>{cleanup();vi.restoreAllMocks()})
describe('separate real extraction sections with offline clients',()=>{
  it('section checkboxes do not extract automatically; one click extracts only selected sections',async()=>{
    const {user,client,sections}=await start()
    expect(sections.analyze).not.toHaveBeenCalled()
    await user.click(screen.getByRole('checkbox',{name:/^Medicines/}))
    await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
    await screen.findByRole('region',{name:'Prescribed investigations review'})
    expect(client.analyze).not.toHaveBeenCalled()
    expect(sections.analyze).toHaveBeenCalledTimes(2)
    expect(screen.getByLabelText('Dosage instructions: Dose quantity as written 1').getAttribute('value')).toBe('')
    expect(screen.getByText(/ambiguous_dose/)).toBeTruthy()
    expect(screen.getByText(/variant_unclear/)).toBeTruthy()
  })
  it('saves/confirms independently and immediately invalidates a corrected section',async()=>{
    const {user,client,sections}=await start()
    await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
    const panel=within(await screen.findByRole('region',{name:'Dosage instructions review'}))
    await user.click(panel.getByRole('button',{name:'Save dosage instructions review'}))
    await waitFor(()=>expect((panel.getByRole('checkbox') as HTMLInputElement).disabled).toBe(false))
    await user.click(panel.getByRole('checkbox'))
    await user.click(panel.getByRole('button',{name:'Confirm dosage instructions'}))
    await panel.findByRole('button',{name:'Confirmed by server'})
    expect(client.confirm).not.toHaveBeenCalled()
    const inv=within(screen.getByRole('region',{name:'Prescribed investigations review'}))
    expect((inv.getByRole('button',{name:'Confirm prescribed investigations'}) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(panel.getByLabelText('Dosage instructions: Medicine name as written 1'),{target:{value:'Corrected fictional name'}})
    expect(panel.queryByRole('button',{name:'Confirmed by server'})).toBeNull()
    await waitFor(()=>expect(sections.invalidate).toHaveBeenCalledTimes(1))
    expect(panel.getByLabelText('Dosage instructions: Medicine name as written 1').getAttribute('value')).toBe('Corrected fictional name')
    expect(panel.getByText(/ambiguous_dose/)).toBeTruthy()
  })
  it('preserves successes on partial failure and retries only the failed scope',async()=>{
    const {user,client,sections}=await start()
    sections.analyze=vi.fn(async s=>s.scope==='investigations'?{...state(s.scope),status:'failed' as const,error:{category:'network_error',message:'Offline test failure'}}:state(s.scope,true))
    await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
    await screen.findByText('Prescribed investigations extraction failed.')
    expect(screen.getByText(/Partial results: completed sections/)).toBeTruthy()
    const medCalls=vi.mocked(client.analyze).mock.calls.length
    sections.analyze=vi.fn(async s=>state(s.scope,true))
    await user.click(screen.getByRole('button',{name:'Retry prescribed investigations'}))
    await waitFor(()=>expect(sections.analyze).toHaveBeenCalledTimes(1))
    expect(vi.mocked(sections.analyze).mock.calls[0][0].scope).toBe('investigations')
    expect(client.analyze).toHaveBeenCalledTimes(medCalls)
    expect(screen.getByLabelText('Dosage instructions: Dose quantity as written 1')).toBeTruthy()
  })
  it('stops sequential calls on quota/configuration failure without erasing medicines',async()=>{
    const {user,client,sections}=await start()
    sections.analyze=vi.fn(async s=>({...state(s.scope),status:'failed' as const,error:{category:'quota_or_rate_limit',message:'Offline quota test'}}))
    await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
    await screen.findByText(/Extraction stopped after a configuration\/quota failure/)
    expect(client.analyze).toHaveBeenCalledTimes(1)
    expect(sections.analyze).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/Extraction succeeded with zero medicines/)).toBeTruthy()
  })
  it('image removal clears all section approvals/results without new extraction',async()=>{
    const {user,sections,client}=await start()
    await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
    await screen.findByRole('region',{name:'Prescribed investigations review'})
    await user.click(screen.getByRole('button',{name:'Remove image'}))
    expect(screen.queryByRole('region',{name:'Dosage instructions review'})).toBeNull()
    expect(screen.queryByRole('region',{name:'Prescribed investigations review'})).toBeNull()
    await waitFor(()=>expect(client.clear).toHaveBeenCalledTimes(1))
    expect(sections.analyze).toHaveBeenCalledTimes(2)
  })
  it('ignores section responses arriving after source removal',async()=>{
    const {user,sections}=await start();let finish!:(s:SectionSnapshot)=>void
    sections.analyze=vi.fn(()=>new Promise<SectionSnapshot>(resolve=>{finish=resolve}))
    await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
    await waitFor(()=>expect(sections.analyze).toHaveBeenCalledTimes(1))
    await user.click(screen.getByRole('button',{name:'Remove image'}))
    finish(state('instructions',true))
    await waitFor(()=>expect(screen.queryByRole('region',{name:'Dosage instructions review'})).toBeNull())
    expect(sections.analyze).toHaveBeenCalledTimes(1)
  })
})
