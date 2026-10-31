export default function OfflineDemoNotice(){
  return import.meta.env.VITE_MEDISAATHI_OFFLINE_DEMO==='1'?<div className="notice" role="status">OFFLINE FICTIONAL DEMO — Mocked OCR, real review and scheduling. No Gemini calls or notification delivery.</div>:null
}
