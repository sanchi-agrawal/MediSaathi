import { describe,expect,it,vi } from 'vitest'
import { createSectionClient,parseSection,validPayload } from './sections'
const payload={schema_version:'medication-instructions-v1',source_image_sha256:'a'.repeat(64),instructions:[],issues:[],confirmation_required:true}
const state={analysis_id:'a',scope:'instructions' as const,revision:'i-r',status:'succeeded' as const,payload,original_payload:payload,error:null,reviewed:false,confirmed:false,extractor_invocations:1}
describe('section transport contracts',()=>{
  it('accepts successful empty envelopes without inferring missing records',()=>{
    expect(validPayload(payload,'instructions')).toBe(true)
    expect(parseSection(state,'instructions','a').payload).toEqual(payload)
    expect(validPayload({...payload,dose:3},'instructions')).toBe(false)
  })
  it('rejects cross-scope, cross-analysis and mixed medicine contracts',()=>{
    expect(validPayload(payload,'investigations')).toBe(false)
    expect(validPayload([{name:'Fictional'}],'instructions')).toBe(false)
    expect(()=>parseSection(state,'instructions','other')).toThrow()
  })
  it('confirmation sends only the current section revision with credentials',async()=>{
    const fetcher=vi.fn(async()=>Response.json(state))
    const client=createSectionClient(fetcher)
    await client.confirm(parseSection(state,'instructions','a'))
    expect(fetcher).toHaveBeenCalledWith('/api/prescriptions/a/sections/instructions/confirm',expect.objectContaining({credentials:'include',body:JSON.stringify({revision:'i-r'})}))
  })
})
