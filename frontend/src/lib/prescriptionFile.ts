import { validateImage, MAX_IMAGE_BYTES } from './image'
export async function validatePrescriptionFile(file:File):Promise<{width:number;height:number}|null>{
  const extension=file.name.split('.').pop()?.toLowerCase()
  if(['png','jpg','jpeg'].includes(extension||''))return validateImage(file)
  if(!['pdf','docx','txt'].includes(extension||''))throw new Error('Use PNG, JPG, PDF, DOCX or TXT.')
  if(!file.size||file.size>MAX_IMAGE_BYTES)throw new Error('Files must be nonempty and no larger than 10 MiB.')
  const bytes=new Uint8Array(await file.slice(0,32).arrayBuffer())
  if(extension==='pdf'&&new TextDecoder().decode(bytes.slice(0,5))!=='%PDF-')throw new Error('This is not a valid PDF.')
  if(extension==='docx'&&!(bytes[0]===80&&bytes[1]===75&&bytes[2]===3&&bytes[3]===4))throw new Error('This is not a valid DOCX.')
  if(extension==='txt'){
    if(file.size>256*1024)throw new Error('Text must not exceed 256 KiB.')
    let text:string
    try{text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer())}catch{throw new Error('TXT must use valid UTF-8 encoding.')}
    if(!text.trim()||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text))throw new Error('The document is blank or contains unsupported binary text.')
  }
  return null // Authoritative document parsing and limits are enforced on Python.
}
