/** Shared original field types and inactive legacy/future-scope/auth interfaces.
 * Connected transports live in prescriptions.ts and sections.ts. Python owns
 * AIIntegration instances, FrontendEvents and snapshot/revision validation.
 */
export type Section = 'medicines' | 'instructions' | 'investigations'
export type Scope = Section | 'strip'
export type Language = 'en' | 'hi' | 'hinglish'
export interface MedicineRecord {
  raw_text: string | null
  name: string | null
  salt: string | null
  strength: string | null
  form: 'tablet' | 'capsule' | 'syrup' | 'drops' | null
  frequency_pattern: string | null
  duration_days: number | null
  timing: string | null
  confidence: number | null
  needs_review: boolean
}
export interface InstructionRecord {
  instruction_id: string
  medicine_name_raw: string | null
  raw_text: string | null
  dose_quantity_raw: string | null
  dose_unit_raw: string | null
  frequency_raw: string | null
  route_raw: string | null
  timing_raw: string | null
  duration_raw: string | null
  uncertainty_reasons: string[]
  needs_review: boolean
  confirmation_required: true
}
export interface InvestigationRecord {
  investigation_id: string
  test_name_raw: string | null
  raw_text: string | null
  order_context_raw: string | null
  specimen_raw: string | null
  variant_raw: string | null
  timing_raw: string | null
  uncertainty_reasons: string[]
  needs_review: boolean
  confirmation_required: true
}
export interface InstructionEnvelope {
  schema_version: 'medication-instructions-v1'
  source_image_sha256: string
  instructions: InstructionRecord[]
  issues: string[]
  confirmation_required: true
}
export interface InvestigationEnvelope {
  schema_version: 'prescribed-investigations-v1'
  source_image_sha256: string
  investigations: InvestigationRecord[]
  issues: string[]
  confirmation_required: true
}
export type SectionPayloads = {
  medicines: MedicineRecord[]
  instructions: InstructionEnvelope
  investigations: InvestigationEnvelope
}
export type ExtractionState<T> =
  | { status: 'idle' }
  | { status: 'analyzing' }
  | { status: 'success'; payload: T; revision: string }
  | { status: 'error'; category: 'validation' | 'network' | 'quota' | 'configuration' | 'api' | 'invalid_response'; message: string }
export interface AIClient {
  readonly connected: boolean
  analyze(image: File, sections: Section[], signal?: AbortSignal): Promise<void>
  review<S extends Section>(scope: S, revision: string, payload: SectionPayloads[S]): Promise<void>
  confirm(scope: Scope, revision: string): Promise<void>
  explain(language: Language, revision: string): Promise<string>
  analyzeStrip(image: File, signal?: AbortSignal): Promise<void>
}
const unavailable = async (): Promise<never> => { throw new Error('Python API is not connected. No AI request was sent.') }
export const aiClient: AIClient = {
  connected: false, analyze: unavailable, review: unavailable, confirm: unavailable,
  explain: unavailable, analyzeStrip: unavailable,
}
export interface AuthClient {
  readonly connected: boolean
  signIn(email: string, password: string): Promise<void>
  signUp(name: string, email: string, password: string): Promise<void>
  signOut(): Promise<void>
}
export const authClient: AuthClient = { connected: false, signIn: unavailable, signUp: unavailable, signOut: unavailable }
