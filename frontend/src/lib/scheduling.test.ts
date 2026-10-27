import { expect,it,vi } from 'vitest'
import { createSchedulingClient,parseScheduling,validPlan,validResult } from './scheduling'
import type { ScheduleContext } from './scheduling'
const context:ScheduleContext={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',ready:true,status:'associated',medicines:[],instructions:[],instruction_issues:[],association:{association_id:'link',medicine_ref:'medicine_001',instruction_id:'i'},plan:null,result:null,error:null}
it('approval sends only current bindings and association, never trusted events or booleans',async()=>{const fetcher=vi.fn(async()=>Response.json(context));await createSchedulingClient(fetcher).approve(context);expect(fetcher).toHaveBeenCalledWith('/api/prescriptions/a/schedule/approve',expect.objectContaining({credentials:'include',body:JSON.stringify({medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',association_id:'link'})}))})
it('rejects forged output and unsafe nonfinite plan values',()=>{expect(validResult({status:'ok',safe_to_take:true})).toBe(false);expect(validPlan({dose_quantity:Infinity})).toBe(false);expect(()=>parseScheduling({...context,ready:false,result:{derived_id:'fake',payload:{status:'ok'}}})).toThrow();expect(()=>parseScheduling({...context,status:'succeeded'})).toThrow()})
it.each([404,405])('classifies FastAPI string-detail HTTP %s instead of the generic Scheduling failed fallback',async status=>{
  const fetcher=vi.fn(async()=>Response.json({detail:status===404?'Not Found':'Method Not Allowed'},{status}))
  await expect(createSchedulingClient(fetcher).current()).rejects.toMatchObject({category:'api_route_unavailable',status,message:expect.stringContaining('HTTP '+status)})
  expect(fetcher).toHaveBeenCalledTimes(1)
})
it.each([401,403,409,422,429,502,503])('keeps a safe category and HTTP %s when the error envelope is missing',async status=>{
  const categories:Record<number,string>={401:'session_expired',403:'origin_rejected',409:'request_conflict',422:'invalid_input',429:'rate_limited',502:'backend_unavailable',503:'backend_unavailable'}
  await expect(createSchedulingClient(vi.fn(async()=>Response.json({detail:null},{status}))).current()).rejects.toMatchObject({category:categories[status],status})
})
it('preserves structured source-safety errors without converting them to transport errors',async()=>{
  await expect(createSchedulingClient(vi.fn(async()=>Response.json({detail:{category:'unsafe_schedule',message:'Source clarification required.'}},{status:422}))).approve(context)).rejects.toMatchObject({category:'unsafe_schedule',status:422,message:'Source clarification required.'})
})
it('does not echo arbitrary proxy HTML or patient/provider text in errors',async()=>{
  const fetcher=vi.fn(async()=>new Response('sensitive upstream body',{status:502}))
  await expect(createSchedulingClient(fetcher).current()).rejects.toMatchObject({category:'backend_unavailable',status:502,message:expect.not.stringContaining('sensitive upstream body')})
  expect(fetcher).toHaveBeenCalledTimes(1)
})
