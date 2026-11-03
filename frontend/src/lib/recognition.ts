import { ApiError } from './prescriptions'
export type RecognitionMode='gemini'|'offline_fixture'|'custom_extractor'
export interface SourceScript{script:'latin'|'devanagari'|'mixed'|'unknown';source:'original_extracted_text';language_verified:false}
export interface NumericPreview{record_index:number;field:string;original:string;digit_reading:string}
export interface RecognitionMetadata{script_observation?:SourceScript;numeric_previews?:NumericPreview[]}
export interface RecognitionCapabilities{mode:RecognitionMode;ui_language_affects_extraction:false;handwriting:'experimental';accuracy_evaluated:false;script_detection_stage:'after_extraction'}
export function createRecognitionClient(fetcher:typeof fetch=(...a)=>fetch(...a)){
  return {async capabilities():Promise<RecognitionCapabilities>{
    let response:Response;try{response=await fetcher('/api/recognition/capabilities',{credentials:'include',cache:'no-store',headers:{'X-MediSaathi-Action':'review'}})}catch{throw new ApiError('network_error','Recognition mode unavailable.')}
    let value:RecognitionCapabilities;try{value=await response.json()}catch{throw new ApiError('invalid_response','Invalid recognition mode.')}
    if(!response.ok||!value||!['gemini','offline_fixture','custom_extractor'].includes(value.mode)||value.ui_language_affects_extraction!==false||value.handwriting!=='experimental'||value.accuracy_evaluated!==false||value.script_detection_stage!=='after_extraction')throw new ApiError('invalid_response','Recognition mode could not be verified.')
    return value
  }}
}
export const recognitionClient=createRecognitionClient()
export type RecognitionClient=ReturnType<typeof createRecognitionClient>
