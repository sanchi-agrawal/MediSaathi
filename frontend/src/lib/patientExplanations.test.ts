import { afterEach,it,expect,vi } from 'vitest'
import { explainMedicine } from './patientExplanations'
import { clockClient } from './clockScheduling'
import type { AnalysisSnapshot } from './prescriptions'
const source:AnalysisSnapshot={analysis_id:'current',revision:'reviewed',status:'succeeded',records:[],original_records:[],reviewed:true,confirmed:true,error:null}
afterEach(()=>vi.unstubAllGlobals())
it('sends exactly one selected medicine and language using cookie credentials',async()=>{
 const response={analysis_id:'current',revision:'reviewed',record_index:2,language:'hi',status:'identity_uncertain',medicine_name:'Unknown',ingredient:null,cached:false,sections:[],sources:[],prescription:{original_medicine_text:null,confirmed_linked_instruction:null}}
 const fetcher=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>new Response(JSON.stringify(response),{status:200}));vi.stubGlobal('fetch',fetcher)
 expect(fetcher).not.toHaveBeenCalled();await explainMedicine(source,2,'hi')
 expect(fetcher).toHaveBeenCalledTimes(1);expect(fetcher.mock.calls[0][1]).toMatchObject({credentials:'include',method:'POST',body:JSON.stringify({revision:'reviewed',record_index:2,language:'hi'})})
})
it('does not retry a quota failure or accept a fake successful explanation',async()=>{
 const fetcher=vi.fn(async()=>new Response(JSON.stringify({detail:{category:'quota_or_rate_limit',message:'Quota unavailable'}}),{status:429}));vi.stubGlobal('fetch',fetcher)
 await expect(explainMedicine(source,0,'en')).rejects.toMatchObject({category:'quota_or_rate_limit',status:429});expect(fetcher).toHaveBeenCalledTimes(1)
})
it('reports unloaded API routes explicitly for both explanation and scheduling',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({detail:'Not Found'}),{status:404})))
 await expect(explainMedicine(source,0,'en')).rejects.toMatchObject({category:'api_route_unavailable',status:404})
 await expect(clockClient.current()).rejects.toMatchObject({category:'api_route_unavailable',status:404})
})
