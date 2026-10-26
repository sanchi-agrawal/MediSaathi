// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PrescriptionFlow from './PrescriptionFlow'
import { ApiError } from '../lib/prescriptions'
import type { AnalysisSnapshot, ExplanationPayload, PrescriptionClient } from '../lib/prescriptions'
import type { MedicineRecord } from '../lib/api'

vi.mock('../lib/image',()=>({validateImage:vi.fn(async()=>({width:4,height:4}))}))
const record:MedicineRecord={raw_text:'Fictional-A BD',name:'Fictional-A',salt:null,strength:null,form:'tablet',frequency_pattern:'BD',duration_days:null,timing:null,confidence:null,needs_review:true}
const snapshot:AnalysisSnapshot={analysis_id:'analysis-a',revision:'revision-a',status:'succeeded',original_records:[record],records:[record],error:null,reviewed:false,confirmed:false}
const explained:ExplanationPayload={schema_version:'prescription-explanation-v1',status:'explained',language:'en',records_fingerprint:'example',medicines:[{record_index:0,fields:[{field:'name',label:'Name',text:'Medicine name: Fictional-A',display_value:'Fictional-A',is_unknown:false}],glossary:null}],issues:[],notice:'Confirmed text only. Not medical advice.'}
function client():PrescriptionClient {
  return {upload:vi.fn(async()=>({...snapshot,status:'not_requested' as const,records:null,original_records:null})),analyze:vi.fn(async()=>snapshot),status:vi.fn(async()=>snapshot),
    invalidate:vi.fn(async()=>({...snapshot,revision:'invalidated'})),review:vi.fn(async(data,records)=>({...data,records,revision:'reviewed',reviewed:true,confirmed:false})),
    confirm:vi.fn(async(data)=>({...data,confirmed:true})),explain:vi.fn(async()=>explained),clear:vi.fn(async()=>{})}
}
async function start(api:PrescriptionClient){
  render(<PrescriptionFlow client={api}/>)
  const user=userEvent.setup()
  await user.upload(screen.getByLabelText('Upload Prescription image'),new File(['fictional-image'],'fictional.png',{type:'image/png'}))
  await screen.findByAltText('Prescription image selected for your review')
  await user.click(screen.getByRole('button',{name:'Analyze with AI'}))
  return user
}
async function saveAndConfirm(api:PrescriptionClient){
  const user=await start(api)
  await screen.findByLabelText('Medicine name 1')
  await user.click(screen.getByRole('button',{name:'Save reviewed records'}))
  await waitFor(()=>expect((screen.getByRole('checkbox',{name:/I have reviewed every field/}) as HTMLInputElement).disabled).toBe(false))
  await user.click(screen.getByRole('checkbox',{name:/I have reviewed every field/}))
  await user.click(screen.getByRole('button',{name:'Confirm medicines'}))
  return user
}
beforeEach(()=>{URL.createObjectURL=vi.fn(()=> 'blob:fictional');URL.revokeObjectURL=vi.fn()})
afterEach(()=>{cleanup();vi.useRealTimers();vi.restoreAllMocks()})
describe('real prescription page workflow with offline client',()=>{
  it('blocks same-tick double submissions before React rerenders',async()=>{
    const api=client();let finish!:(value:AnalysisSnapshot)=>void
    api.analyze=vi.fn(()=>new Promise<AnalysisSnapshot>(resolve=>{finish=resolve}))
    render(<PrescriptionFlow client={api}/>);const user=userEvent.setup()
    await user.upload(screen.getByLabelText('Upload Prescription image'),new File(['x'],'x.png',{type:'image/png'}))
    await screen.findByAltText('Prescription image selected for your review')
    const button=screen.getByRole('button',{name:'Analyze with AI'})
    act(()=>{button.dispatchEvent(new MouseEvent('click',{bubbles:true}));button.dispatchEvent(new MouseEvent('click',{bubbles:true}))})
    await waitFor(()=>expect(api.analyze).toHaveBeenCalledTimes(1))
    expect(api.upload).toHaveBeenCalledTimes(1)
    expect((screen.getByRole('button',{name:'Analyzing image…'}) as HTMLButtonElement).disabled).toBe(true)
    finish(snapshot);await screen.findByLabelText('Medicine name 1')
  })
  it('shows honest elapsed waiting feedback and sends no automatic retry',async()=>{
    vi.useFakeTimers({toFake:['setInterval','clearInterval']})
    let now=0;vi.spyOn(performance,'now').mockImplementation(()=>now)
    const api=client();let finish!:(value:AnalysisSnapshot)=>void
    api.analyze=vi.fn(()=>new Promise<AnalysisSnapshot>(resolve=>{finish=resolve}))
    await start(api)
    await screen.findByText('Waiting for Gemini extraction…')
    now=22000;act(()=>{vi.advanceTimersByTime(22000)})
    expect(screen.getByText(/22 s elapsed/)).toBeTruthy()
    expect(screen.getByText(/request is still pending/)).toBeTruthy()
    expect(api.analyze).toHaveBeenCalledTimes(1)
    finish(snapshot);await screen.findByLabelText('Medicine name 1')
  })
  it('never analyzes on mount, upload or language changes',async()=>{
    const api=client();render(<PrescriptionFlow client={api}/>);const user=userEvent.setup()
    await user.click(screen.getByRole('button',{name:'हिन्दी'}))
    await user.upload(screen.getByLabelText('Upload Prescription image'),new File(['x'],'x.png',{type:'image/png'}))
    await screen.findByAltText('Prescription image selected for your review')
    expect(api.analyze).not.toHaveBeenCalled();expect(api.upload).not.toHaveBeenCalled()
    expect((screen.getByRole('button',{name:'Analyze with AI'}) as HTMLButtonElement).disabled).toBe(false)
  })
  it('shows all ten fields and preserves unknowns, then saves, confirms and explains',async()=>{
    const api=client();const user=await saveAndConfirm(api)
    await screen.findByRole('button',{name:'Confirmed by server'})
    expect(screen.getByLabelText('Printed ingredient 1').getAttribute('value')).toBe('')
    expect(screen.getByText('Extraction confidence (uncalibrated)')).toBeTruthy()
    expect(screen.getByText('Extraction review flag')).toBeTruthy()
    expect(api.review).toHaveBeenCalledWith(snapshot,[record])
    await user.click(screen.getByRole('button',{name:'Explain confirmed medicines'}))
    expect(await screen.findByText(explained.notice)).toBeTruthy()
    expect(api.explain).toHaveBeenCalledWith(expect.objectContaining({confirmed:true}),'en')
  })
  it('removes confirmation/explanation immediately on edit and invalidates the server',async()=>{
    const api=client();const user=await saveAndConfirm(api)
    await screen.findByRole('button',{name:'Confirmed by server'})
    await user.click(screen.getByRole('button',{name:'Explain confirmed medicines'}))
    await screen.findByText(explained.notice)
    fireEvent.change(screen.getByLabelText('Medicine name 1'),{target:{value:'Corrected fictional text'}})
    expect(screen.queryByText(explained.notice)).toBeNull()
    expect((screen.getByRole('button',{name:'Confirm medicines'}) as HTMLButtonElement).disabled).toBe(true)
    await waitFor(()=>expect(api.invalidate).toHaveBeenCalledOnce())
    expect((screen.getByRole('button',{name:'Explain confirmed medicines'}) as HTMLButtonElement).disabled).toBe(true)
  })
  it('does not show server confirmation when confirm fails',async()=>{
    const api=client();api.confirm=vi.fn(async()=>{throw new ApiError('stale_result','Review current records.')})
    await saveAndConfirm(api)
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.queryByRole('button',{name:'Confirmed by server'})).toBeNull()
    expect(api.explain).not.toHaveBeenCalled()
  })
  it('does not re-extract or clear a successful confirmed scope on another click',async()=>{
    const api=client();const user=await saveAndConfirm(api)
    await screen.findByRole('button',{name:'Confirmed by server'})
    await user.click(screen.getByRole('button',{name:'Explain confirmed medicines'}))
    await screen.findByText(explained.notice)
    const button=screen.getByRole('button',{name:'Analyze with AI'})
    expect((button as HTMLButtonElement).disabled).toBe(true)
    await user.click(button)
    expect(api.analyze).toHaveBeenCalledTimes(1)
    expect(screen.getByText(explained.notice)).toBeTruthy()
  })
  it('distinguishes successful empty extraction from API failure and retries only on click',async()=>{
    const api=client();api.analyze=vi.fn().mockResolvedValueOnce({...snapshot,status:'failed',records:null,original_records:null,error:{category:'api_error',message:'Provider unavailable.'}}).mockResolvedValueOnce({...snapshot,records:[],original_records:[]})
    const user=await start(api)
    await screen.findByText('Extraction failed — no successful result.')
    expect(screen.queryByText(/Extraction succeeded with zero/)).toBeNull()
    expect(api.analyze).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button',{name:'Retry AI analysis'}))
    await screen.findByText(/Extraction succeeded with zero medicines/)
    expect(api.analyze).toHaveBeenCalledTimes(2)
    expect(api.upload).toHaveBeenCalledTimes(1)
  })
  it('ignores an old extraction response after removing its source',async()=>{
    const api=client();let resolve!:(value:AnalysisSnapshot)=>void
    api.analyze=vi.fn(()=>new Promise<AnalysisSnapshot>(r=>{resolve=r}))
    const user=await start(api)
    await waitFor(()=>expect(api.analyze).toHaveBeenCalledOnce())
    await user.click(screen.getByRole('button',{name:'Remove image'}))
    resolve(snapshot)
    await waitFor(()=>expect(api.clear).toHaveBeenCalledOnce())
    expect(screen.queryByLabelText('Medicine name 1')).toBeNull()
  })
  it('passes selected Hindi and Hinglish languages explicitly',async()=>{
    const api=client();const user=await saveAndConfirm(api)
    await screen.findByRole('button',{name:'Confirmed by server'})
    await user.click(screen.getByRole('button',{name:'हिन्दी'}))
    await user.click(screen.getByRole('button',{name:'Explain confirmed medicines'}))
    await waitFor(()=>expect(api.explain).toHaveBeenLastCalledWith(expect.anything(),'hi'))
    await waitFor(()=>expect((screen.getByRole('button',{name:'Hinglish'}) as HTMLButtonElement).disabled).toBe(false))
    await user.click(screen.getByRole('button',{name:'Hinglish'}))
    await user.click(screen.getByRole('button',{name:'Explain confirmed medicines'}))
    await waitFor(()=>expect(api.explain).toHaveBeenLastCalledWith(expect.anything(),'hinglish'))
  })
})
