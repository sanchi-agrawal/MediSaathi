// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { render,screen,cleanup,waitFor,fireEvent } from '@testing-library/react'
import ImageUploader from '../components/ImageUploader'
import { createPrescriptionClient } from '../lib/prescriptions'
import { setLanguage } from '../lib/language'
import PrescriptionFlow from './PrescriptionFlow'
import type { PrescriptionClient,AnalysisSnapshot } from '../lib/prescriptions'
vi.mock('../lib/prescriptionFile',()=>({validatePrescriptionFile:vi.fn(async()=>null)}))
afterEach(()=>{cleanup();setLanguage('en');vi.restoreAllMocks()})
it('selects a document without uploading or extracting it and shows the filename',async()=>{
 URL.createObjectURL=vi.fn(()=>'blob:demo');URL.revokeObjectURL=vi.fn()
 const changed=vi.fn();render(<ImageUploader allowDocuments onChange={changed}/>)
 const input=screen.getByLabelText('Upload Prescription image')
 expect(input.getAttribute('accept')).toContain('.pdf')
 fireEvent.change(input,{target:{files:[new File(['demo'],'synthetic.pdf',{type:'application/pdf'})]}})
 await screen.findByText('synthetic.pdf')
 expect(screen.queryByRole('img')).toBeNull()
 await waitFor(()=>expect(changed).toHaveBeenCalledTimes(2))
 expect(changed.mock.calls[1][0].name).toBe('synthetic.pdf')
})
it('keeps the strip uploader image-only',()=>{
 render(<ImageUploader onChange={vi.fn()}/>);expect(screen.getByLabelText('Upload Prescription image').getAttribute('accept')).toBe('image/png,image/jpeg')
})
it('sends the document bytes and safe filename header with session cookies',async()=>{
 const fetcher=vi.fn(async()=>Response.json({analysis_id:'a',revision:'r',status:'not_requested',original_records:null,records:null,error:null,reviewed:false,confirmed:false}))
 const file=new File(['demo'],'test.txt',{type:'text/plain'})
 await createPrescriptionClient(fetcher).upload(file)
 expect(fetcher).toHaveBeenLastCalledWith('/api/prescriptions',expect.objectContaining({body:file,credentials:'include',headers:expect.objectContaining({'Content-Type':'text/plain','X-MediSaathi-Filename':'test.txt'})}))
 expect(fetcher).toHaveBeenCalledTimes(2)
})
it('analyzes a selected document only on explicit action and renders ordinary medicine review',async()=>{
 URL.createObjectURL=vi.fn(()=>'blob:demo');URL.revokeObjectURL=vi.fn()
 const state:AnalysisSnapshot={analysis_id:'a',revision:'r',status:'not_requested',records:null,original_records:null,error:null,reviewed:false,confirmed:false}
 const record={raw_text:'Dolo सुबह',name:'Dolo',salt:null,strength:'650 mg',form:'tablet' as const,frequency_pattern:null,duration_days:5,timing:null,confidence:null,needs_review:true}
 const api={current:vi.fn(async()=>null),image:vi.fn(),upload:vi.fn(async()=>state),analyze:vi.fn(async()=>({...state,status:'succeeded',records:[record],original_records:[record]})),clear:vi.fn(async()=>{})} as unknown as PrescriptionClient
 render(<PrescriptionFlow client={api}/>);
 fireEvent.change(screen.getByLabelText('Upload Prescription image'),{target:{files:[new File(['demo'],'a.txt',{type:'text/plain'})]}})
 await screen.findByText('a.txt');expect(api.upload).not.toHaveBeenCalled();expect(api.analyze).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'Analyze Prescription with AI'}))
 expect(await screen.findByLabelText('Medicine name 1')).toHaveProperty('value','Dolo')
 expect(api.analyze).toHaveBeenCalledTimes(1);expect(screen.getByRole('button',{name:'Confirm medicines'})).toHaveProperty('disabled',true)
})
