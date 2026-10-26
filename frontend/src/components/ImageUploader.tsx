import { useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, FileImage, RotateCw, Upload, X, ZoomIn, ZoomOut } from 'lucide-react'
import { validateImage } from '../lib/image'

export default function ImageUploader({ label = 'Prescription image', onChange }: { label?: string; onChange: (file: File | null) => void }) {
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
  async function choose(next:File|undefined) {
    if(!next)return
    const current=++generation.current
    setFile(null);onChange(null);setError('');setChecking(true);setZoom(1);setRotation(0)
    try {const size=await validateImage(next);if(current!==generation.current)return;setFile(next);setDimensions(`${size.width} × ${size.height} px`);onChange(next)}
    catch(error){if(current===generation.current)setError(error instanceof Error?error.message:'This image could not be opened.')}
    finally{if(current===generation.current)setChecking(false)}
  }
  function clear(){generation.current++;setFile(null);onChange(null);setError('');setChecking(false)}
  return <div className="image-uploader"><input ref={uploadRef} type="file" accept="image/png,image/jpeg" hidden aria-label={`Upload ${label}`} onChange={e=>{void choose(e.target.files?.[0]);e.target.value=''}}/><input ref={cameraRef} type="file" accept="image/png,image/jpeg" capture="environment" hidden aria-label={`Take photo of ${label}`} onChange={e=>{void choose(e.target.files?.[0]);e.target.value=''}}/>
    {!file?<div className={`dropzone ${dragging?'dragging':''}`} onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);void choose(e.dataTransfer.files[0])}}><div className="upload-orbit"><Upload size={28}/></div><h3>{checking?'Checking your image…':'A clearer picture starts here.'}</h3><p>Drop your {label.toLowerCase()} here,<br/>or choose how you’d like to add it.</p><div className="upload-actions"><button className="button" onClick={()=>uploadRef.current?.click()} disabled={checking}><Upload size={16}/> Upload image</button><button className="button secondary" onClick={()=>cameraRef.current?.click()} disabled={checking}><Camera size={17}/> Take photo</button></div><span className="micro">PNG OR JPEG · UP TO 10 MiB · 8 MILLION PIXELS</span></div>:<div className="image-preview"><div className="preview-stage"><img src={url||undefined} alt={`${label} selected for your review`} style={{transform:`rotate(${rotation}deg) scale(${zoom})`}}/></div><div className="preview-toolbar"><span><FileImage size={15}/><strong title={file.name}>{file.name}</strong><small>{dimensions}</small></span><div><button className="icon-button" aria-label="Zoom out" disabled={zoom<=.5} onClick={()=>setZoom(v=>Math.max(.5,v-.25))}><ZoomOut size={17}/></button><output aria-label="Zoom level">{Math.round(zoom*100)}%</output><button className="icon-button" aria-label="Zoom in" disabled={zoom>=3} onClick={()=>setZoom(v=>Math.min(3,v+.25))}><ZoomIn size={17}/></button><button className="icon-button" aria-label="Rotate preview clockwise" onClick={()=>setRotation(v=>(v+90)%360)}><RotateCw size={17}/></button><button className="icon-button" aria-label="Remove image" onClick={clear}><X size={17}/></button></div></div><p className="preview-valid"><CheckCircle2 size={14}/> Image opens in this browser. Server validation is still required.</p><p className="form-footnote">Zoom and rotation affect the preview only. Original image bytes are preserved.</p><button className="text-link" onClick={()=>uploadRef.current?.click()}>Choose a different image</button></div>}
    {error&&<div className="error-message" role="alert">{error}</div>}<p className="upload-caption">Use a well-lit, sharp photo with all text visible. Camera capture depends on your device; desktop browsers may open a file picker. Python validates decoding and single-frame limits; unclear extracted text still needs your review.</p>
  </div>
}
