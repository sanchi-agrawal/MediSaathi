// @vitest-environment jsdom
import { expect,it,vi } from 'vitest'
import { createPrescriptionClient } from './prescriptions'
const state={analysis_id:'a',revision:'r',status:'succeeded' as const,original_records:[],records:[],error:null,reviewed:true,confirmed:true}
it('restores with credentialed GET and never creates a session, analysis or OCR request',async()=>{
  const fetcher=vi.fn(async()=>Response.json(state));const restored=await createPrescriptionClient(fetcher).current()
  expect(restored?.analysis_id).toBe('a');expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher).toHaveBeenCalledWith('/api/prescriptions/current',expect.objectContaining({method:'GET',credentials:'include',cache:'no-store'}))
})
it('treats missing/expired sessions as unavailable and never silently replaces their identity',async()=>{
  for(const status of [401,404]){
    const fetcher=vi.fn(async()=>Response.json({detail:{category:status===401?'session_expired':'no_current_prescription',message:'Unavailable'}},{status}))
    expect(await createPrescriptionClient(fetcher).current()).toBeNull();expect(fetcher).toHaveBeenCalledTimes(1)
  }
})
it('binds restored images to the expected analysis and revision and includes the session cookie',async()=>{
  const fetcher=vi.fn(async()=>new Response(new Uint8Array([1,2]),{headers:{'Content-Type':'image/png'}}))
  const image=await createPrescriptionClient(fetcher).image(state)
  expect(image.name).toBe('current-prescription.png')
  expect(fetcher).toHaveBeenCalledWith('/api/prescriptions/current/image?analysis_id=a&revision=r',expect.objectContaining({credentials:'include',cache:'no-store'}))
})
it('rejects an explanation in the wrong language rather than displaying unchanged English as Hindi',async()=>{
  const payload={schema_version:'prescription-explanation-v1',status:'empty',language:'en',records_fingerprint:'f',medicines:[],issues:[],notice:'Confirmed only'}
  const fetcher=vi.fn(async()=>Response.json({analysis_id:'a',revision:'r',payload}))
  await expect(createPrescriptionClient(fetcher).explain(state,'hi')).rejects.toMatchObject({category:'invalid_response'})
})
