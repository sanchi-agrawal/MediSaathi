// @vitest-environment jsdom
import { beforeEach,afterEach,it,expect,vi } from 'vitest'
import { cleanup,render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PrescriptionFlow from './PrescriptionFlow'
import RecognitionPanel,{NumeralReading} from '../components/RecognitionPanel'
import { LanguageToggle } from '../components/LanguageToggle'
import { setLanguage } from '../lib/language'
import { createRecognitionClient } from '../lib/recognition'
import type { RecognitionClient,RecognitionCapabilities } from '../lib/recognition'
import type { AnalysisSnapshot,PrescriptionClient } from '../lib/prescriptions'
vi.mock('../lib/image',()=>({validateImage:vi.fn(async()=>({width:8,height:8}))}))
const raw='डेमो-ए १० मि.ग्रा. गोली\nसुबह और रात १ गोली, खाने के बाद, दिन में २ बार, ५ दिन तक लें।'
const record={raw_text:raw,name:'डेमो-ए',salt:null,strength:'१० मि.ग्रा.',form:'tablet' as const,frequency_pattern:'दिन में २ बार',duration_days:5,timing:'सुबह और रात १ गोली, खाने के बाद',confidence:null,needs_review:true}
const initial:AnalysisSnapshot={analysis_id:'a',revision:'v1',status:'not_requested',records:null,original_records:null,error:null,reviewed:false,confirmed:false}
const result:AnalysisSnapshot={...initial,status:'succeeded',records:[record],original_records:[record],script_observation:{script:'devanagari',source:'original_extracted_text',language_verified:false},numeric_previews:[{record_index:0,field:'strength',original:'१० मि.ग्रा.',digit_reading:'10 मि.ग्रा.'}]}
function capabilities(mode:RecognitionCapabilities['mode']='offline_fixture'):RecognitionClient{return {capabilities:vi.fn(async():Promise<RecognitionCapabilities>=>({mode,ui_language_affects_extraction:false,handwriting:'experimental',accuracy_evaluated:false,script_detection_stage:'after_extraction'}))}}
function client():PrescriptionClient{return {current:vi.fn(async()=>null),image:vi.fn(),upload:vi.fn(async()=>initial),analyze:vi.fn(async()=>result),status:vi.fn(),review:vi.fn(async(_s,records)=>({...result,records,reviewed:true})),confirm:vi.fn(),invalidate:vi.fn(),explain:vi.fn(),clear:vi.fn(async()=>{})}}
beforeEach(()=>{setLanguage('en');URL.createObjectURL=vi.fn(()=>'blob:fixture');URL.revokeObjectURL=vi.fn()})
afterEach(()=>{cleanup();vi.restoreAllMocks();setLanguage('en')})
it('shows the real AI action in English and Hindi with no information panel or automatic extraction',async()=>{
  const c=client();render(<><LanguageToggle/><PrescriptionFlow client={c} recognition={capabilities('gemini')}/></>)
  await screen.findByRole('button',{name:'Analyze Prescription with AI'})
  expect(screen.queryByText('English, Hindi and mixed prescriptions')).toBeNull()
  expect(screen.queryByRole('region',{name:'Prescription recognition mode'})).toBeNull()
  await userEvent.setup().click(screen.getByRole('button',{name:'हिंदी'}))
  expect(screen.getByRole('button',{name:'AI से पर्चे का विश्लेषण करें'})).toBeTruthy()
  expect(c.upload).not.toHaveBeenCalled();expect(c.analyze).not.toHaveBeenCalled()
})
it('labels offline output as simulation and recognizes original Hindi independently of the English interface',async()=>{
  const c=client(),mode=capabilities();render(<PrescriptionFlow client={c} recognition={mode}/>);await screen.findByRole('button',{name:'Run fixture simulation'})
  expect(screen.queryByText('English, Hindi and mixed prescriptions')).toBeNull();expect(c.analyze).not.toHaveBeenCalled()
  const u=userEvent.setup();await u.upload(screen.getByLabelText('Upload Prescription image'),new File(['fixture'],'hindi.png',{type:'image/png'}));await u.click(screen.getByRole('button',{name:'Run fixture simulation'}))
  await screen.findByLabelText('Medicine name 1');expect((screen.getByLabelText('Medicine name 1') as HTMLInputElement).value).toBe('डेमो-ए')
  expect((screen.getByLabelText('Original medicine text 1') as HTMLTextAreaElement).value).toBe(raw)
  expect(screen.getByText('10 मि.ग्रा.')).toBeTruthy()
  expect(c.upload).toHaveBeenCalledTimes(1);expect(vi.mocked(c.upload).mock.calls[0]).toHaveLength(2)
  expect(c.analyze).toHaveBeenCalledTimes(1);expect(c.explain).not.toHaveBeenCalled()
})
it('keeps raw and reviewed Hindi values unchanged across interface toggles, and permits explicit correction',async()=>{
  const c=client();vi.mocked(c.current).mockResolvedValue(result);render(<><LanguageToggle/><PrescriptionFlow client={c} recognition={capabilities()}/></>)
  await screen.findByLabelText('Medicine name 1');const u=userEvent.setup();await u.click(screen.getByRole('button',{name:'हिंदी'}))
  expect((screen.getByLabelText('दवा का नाम 1') as HTMLInputElement).value).toBe('डेमो-ए')
  expect((screen.getByLabelText('लिखी हुई क्षमता 1') as HTMLInputElement).value).toBe('१० मि.ग्रा.')
  const timing=screen.getByLabelText('लिखा हुआ समय 1');await u.clear(timing);await u.type(timing,'सुबह खाने के बाद');await u.click(screen.getByRole('button',{name:'जाँचे गए रिकॉर्ड सहेजें'}))
  await waitFor(()=>expect(c.review).toHaveBeenCalledWith(result,[{...record,timing:'सुबह खाने के बाद'}]))
  expect(c.analyze).not.toHaveBeenCalled();expect(c.confirm).not.toHaveBeenCalled()
})
it('does not claim provider success when provenance is unavailable or a request fails',async()=>{
  const mode=capabilities();vi.mocked(mode.capabilities).mockRejectedValue(new Error('offline'))
  const onMode=vi.fn();const page=render(<RecognitionPanel client={mode} onMode={onMode}/>);await waitFor(()=>expect(onMode).toHaveBeenCalledWith(null))
  expect(page.container.innerHTML).toBe('')
  cleanup();const c=client();vi.mocked(c.current).mockResolvedValue({...initial,status:'failed',error:{category:'api_error',message:'Provider failed'}})
  render(<PrescriptionFlow client={c} recognition={capabilities('gemini')}/>);await screen.findByText('Extraction failed — no successful result.');expect(screen.queryByLabelText('Medicine name 1')).toBeNull()
})
it('reading aids exclude brand names and invalid metadata and never alter original values',()=>{
  const metadata={numeric_previews:[{record_index:0,field:'name',original:'डेमो-१',digit_reading:'डेमो-1'},{record_index:0,field:'dose_quantity_raw',original:'१/२',digit_reading:'1/2'}]}
  render(<NumeralReading metadata={metadata}/>);expect(screen.getByText('१/२')).toBeTruthy();expect(screen.getByText('1/2')).toBeTruthy();expect(screen.queryByText('डेमो-1')).toBeNull();expect(metadata.numeric_previews[1].original).toBe('१/२')
})
it('checks mode through a session-bound GET with no image, UI language, or extraction request',async()=>{
  const value=await capabilities('gemini').capabilities();const fetcher=vi.fn(async()=>new Response(JSON.stringify(value)))
  expect((await createRecognitionClient(fetcher).capabilities()).mode).toBe('gemini')
  expect(fetcher).toHaveBeenCalledWith('/api/recognition/capabilities',expect.objectContaining({credentials:'include',cache:'no-store'}))
  expect(fetcher).toHaveBeenCalledTimes(1)
})
