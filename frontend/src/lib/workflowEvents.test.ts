// @vitest-environment jsdom
import { expect,it,vi } from 'vitest'
import { subscribeSchedulingInvalidation } from './workflowEvents'
import { createPrescriptionClient } from './prescriptions'
import type { AnalysisSnapshot } from './prescriptions'
import { createSectionClient } from './sections'
import type { SectionSnapshot } from './sections'

it('hides schedules before mutation errors, without putting source data into notifications',async()=>{
  const notice=vi.fn();const stop=subscribeSchedulingInvalidation(notice)
  const fetcher=vi.fn(async()=>{throw new Error('offline')})
  await expect(createPrescriptionClient(fetcher).invalidate({analysis_id:'a',revision:'r'} as AnalysisSnapshot)).rejects.toThrow()
  expect(notice).toHaveBeenCalledTimes(1)
  expect(notice.mock.calls[0]).toEqual([])
  stop()
})
it('invalidates for instruction edits but leaves investigation operations independent',async()=>{
  const notice=vi.fn();const stop=subscribeSchedulingInvalidation(notice)
  const api=createSectionClient(vi.fn(async()=>{throw new Error('offline')}))
  await expect(api.invalidate({analysis_id:'a',revision:'r',scope:'investigations'} as SectionSnapshot)).rejects.toThrow()
  expect(notice).not.toHaveBeenCalled()
  await expect(api.invalidate({analysis_id:'a',revision:'r',scope:'instructions'} as SectionSnapshot)).rejects.toThrow()
  expect(notice).toHaveBeenCalledTimes(1)
  stop()
})
it('does not block API invalidation when cross-tab messaging is denied',async()=>{
  const descriptor=Object.getOwnPropertyDescriptor(window,'BroadcastChannel')
  Object.defineProperty(window,'BroadcastChannel',{configurable:true,value:class{constructor(){throw new Error('Disabled')}}})
  try{
    const notice=vi.fn();const stop=subscribeSchedulingInvalidation(notice)
    const fetcher=vi.fn(async()=>{throw new Error('offline')})
    await expect(createPrescriptionClient(fetcher).invalidate({analysis_id:'a',revision:'r'} as AnalysisSnapshot)).rejects.toThrow()
    expect(fetcher).toHaveBeenCalledTimes(1);expect(notice).toHaveBeenCalledTimes(1);stop()
  }finally{if(descriptor)Object.defineProperty(window,'BroadcastChannel',descriptor);else Reflect.deleteProperty(window,'BroadcastChannel')}
})
