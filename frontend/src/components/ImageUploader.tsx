import { useLanguage as useUiLanguage, translate as tr, translateError as uiError } from '../lib/language'
import { useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, FileImage, RotateCw, Upload, X, ZoomIn, ZoomOut } from 'lucide-react'
import { validateImage } from '../lib/image'
import { validatePrescriptionFile } from '../lib/prescriptionFile'

export default function ImageUploader({ label = 'Prescription image', onChange, restoredFile,disabled=false,allowDocuments=false }: { label?: string; onChange: (file: File | null) => void; restoredFile?:File|null;disabled?:boolean;allowDocuments?:boolean }) {
  useUiLanguage()

  const uploadRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const generation = useRef(0)
  const [file,setFile] = useState<File|null>(null)
  const [url,setUrl] = useState('')
  const [error,setError] = useState('')
  const [checking,setChecking] = useState(false)
  const [dimensions,setDimensions] = useState('')
  const [zoom,setZoom] = useState(1)
  const [rotation,setRotation] = useState(0)
  const [dragging,setDragging] = useState(false)
  useEffect(()=>{if(!file){setUrl('');return}const next=URL.createObjectURL(file);setUrl(next);return()=>URL.revokeObjectURL(next)},[file])
  useEffect(()=>()=>{generation.current++},[])
  useEffect(()=>{if(restoredFile){generation.current++;setFile(restoredFile);setError('');setChecking(false);setDimensions('Restored from current server session');setZoom(1);setRotation(0)}},[restoredFile])
  async function choose(next:File|undefined) {
    if(disabled)return
    if(!next)return
    const current=++generation.current
    setFile(null);onChange(null);setError('');setChecking(true);setZoom(1);setRotation(0)
    try {const size=await (allowDocuments?validatePrescriptionFile(next):validateImage(next));if(current!==generation.current)return;setFile(next);setDimensions(size?`${size.width} × ${size.height} px`:next.name.split('.').pop()?.toUpperCase()||'Document');onChange(next)}
    catch(error){if(current===generation.current)setError(error instanceof Error?error.message:'This image could not be opened.')}
    finally{if(current===generation.current)setChecking(false)}
  }
  function clear(){generation.current++;setFile(null);onChange(null);setError('');setChecking(false)}
  return <div className="image-uploader"><input ref={uploadRef} type="file" accept={allowDocuments?"image/png,image/jpeg,.pdf,.docx,.txt":"image/png,image/jpeg"} hidden aria-label={tr("Upload {0}",[tr(label)])} onChange={e=>{void choose(e.target.files?.[0]);e.target.value=''}}/><input ref={cameraRef} type="file" accept="image/png,image/jpeg" capture="environment" hidden aria-label={tr("Take photo of {0}",[tr(label)])} onChange={e=>{void choose(e.target.files?.[0]);e.target.value=''}}/>
    {!file?<div className={`dropzone ${dragging?'dragging':''}`} onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);void choose(e.dataTransfer.files[0])}}><div className="upload-orbit"><Upload size={28}/></div><h3>{checking?tr(allowDocuments?"Checking your file…":"Checking your image…"):tr("A clearer picture starts here.")}</h3><p>{tr("Drop your {0} here,",[tr(label)])}<br/>{tr("or choose how you’d like to add it.")}</p><div className="upload-actions"><button className="button" onClick={()=>uploadRef.current?.click()} disabled={checking}><Upload size={16}/>{tr(allowDocuments?"Upload prescription":" Upload image")}</button><button className="button secondary" onClick={()=>cameraRef.current?.click()} disabled={checking}><Camera size={17}/>{tr(" Take photo")}</button></div><span className="micro">{tr(allowDocuments?"PNG · JPG · PDF · DOCX · TXT · UP TO 10 MiB":"PNG OR JPEG · UP TO 10 MiB · 8 MILLION PIXELS")}</span></div>:<div className="image-preview"><div className="preview-stage">{!allowDocuments||file.type.startsWith('image/')||/\.(png|jpe?g)$/i.test(file.name)?<img src={url||undefined} alt={tr("{0} selected for your review",[tr(label)])} style={{transform:`rotate(${rotation}deg) scale(${zoom})`}}/>:<p>{tr("Document selected. Python validates and prepares the source when you analyze.")}</p>}</div><div className="preview-toolbar"><span><FileImage size={15}/><strong title={file.name}>{file.name}</strong><small>{tr(dimensions)}</small></span><div><button className="icon-button" aria-label={tr("Zoom out")} disabled={zoom<=.5} onClick={()=>setZoom(v=>Math.max(.5,v-.25))}><ZoomOut size={17}/></button><output aria-label={tr("Zoom level")}>{Math.round(zoom*100)}%</output><button className="icon-button" aria-label={tr("Zoom in")} disabled={zoom>=3} onClick={()=>setZoom(v=>Math.min(3,v+.25))}><ZoomIn size={17}/></button><button className="icon-button" aria-label={tr("Rotate preview clockwise")} onClick={()=>setRotation(v=>(v+90)%360)}><RotateCw size={17}/></button><button className="icon-button" aria-label={tr("Remove image")} onClick={clear}><X size={17}/></button></div></div><p className="preview-valid"><CheckCircle2 size={14}/>{tr(allowDocuments?"File selected. Server validation is still required.":" Image opens in this browser. Server validation is still required.")}</p><p className="form-footnote">{tr("Zoom and rotation affect the preview only. Original image bytes are preserved.")}</p><button className="text-link" onClick={()=>uploadRef.current?.click()}>{tr(allowDocuments?"Choose a different file":"Choose a different image")}</button></div>}
    {error&&<div className="error-message" role="alert">{uiError(error)}</div>}<p className="upload-caption">{tr(allowDocuments?"PDF: up to 3 pages. DOCX/TXT: UTF-8 text up to 256 KiB. Images keep their existing limits.":"Use a well-lit, sharp photo with all text visible. Camera capture depends on your device; desktop browsers may open a file picker. Python validates decoding and single-frame limits; unclear extracted text still needs your review.")}</p>
  </div>
}
