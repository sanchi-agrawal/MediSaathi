import { describe, expect, it, vi } from 'vitest'
import { ApiError, createPrescriptionClient, isMedicine } from './prescriptions'
import type { AnalysisSnapshot } from './prescriptions'

const record={raw_text:'Fictional text',name:null,salt:null,strength:null,form:null,frequency_pattern:null,duration_days:null,timing:null,confidence:null,needs_review:true}
const state:AnalysisSnapshot={analysis_id:'a',revision:'r',status:'succeeded',original_records:[record],records:[record],error:null,reviewed:true,confirmed:false}
describe('medicine HTTP boundary',()=>{
  it('uploads the original File as raw image bytes without JSON or multipart conversion',async()=>{
    const file=new File([new Uint8Array([137,80,78,71,13,10,26,10])],'fictional.png',{type:'image/png'})
    const fetcher=vi.fn(async()=>Response.json(state))
    const client=createPrescriptionClient(fetcher)
    await client.upload(file)
    expect(fetcher).toHaveBeenLastCalledWith('/api/prescriptions',expect.objectContaining({body:file,headers:expect.objectContaining({'Content-Type':'image/png'}),credentials:'include'}))
    expect(fetcher.mock.calls.length).toBe(2)
  })
  it('preserves nulls and rejects forged fields and coerced types',()=>{
    expect(isMedicine(record)).toBe(true)
    expect(isMedicine({...record,dose:4})).toBe(false)
    expect(isMedicine({...record,duration_days:true})).toBe(false)
    expect(isMedicine({...record,salt:''})).toBe(false)
  })
  it('sends only revision in a confirmation request, with cookie credentials',async()=>{
    const fetcher=vi.fn(async()=>Response.json({...state,confirmed:true}))
    const client=createPrescriptionClient(fetcher)
    await client.confirm(state)
    expect(fetcher).toHaveBeenCalledWith('/api/prescriptions/a/confirm',expect.objectContaining({credentials:'include',cache:'no-store',body:JSON.stringify({revision:'r'})}))
  })
  it('does not turn an HTTP failure into empty extraction',async()=>{
    const client=createPrescriptionClient(vi.fn(async()=>Response.json({detail:{category:'session_expired',message:'Start a new session.'}},{status:401})))
    await expect(client.analyze(state)).rejects.toMatchObject({category:'session_expired',status:401})
  })
  it('rejects malformed server medicine payloads',async()=>{
    const client=createPrescriptionClient(vi.fn(async()=>Response.json({...state,records:[{...record,dose:4}]})))
    await expect(client.status(state)).rejects.toMatchObject({category:'invalid_response'})
  })
  it('separates network failures from successful empty results',async()=>{
    const offline=createPrescriptionClient(vi.fn(async()=>{throw new Error('private error')}))
    await expect(offline.status(state)).rejects.toBeInstanceOf(ApiError)
    const empty=createPrescriptionClient(vi.fn(async()=>Response.json({...state,records:[],original_records:[]})))
    expect((await empty.status(state)).records).toEqual([])
  })
})
