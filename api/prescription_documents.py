"""Content-validated prescription inputs. All retained source state is session RAM."""
import base64,hashlib,json,re,subprocess,sys
from io import BytesIO
from pathlib import Path,PurePosixPath
from zipfile import ZipFile,BadZipFile
from defusedxml import ElementTree as XML
from PIL import Image,ImageDraw,ImageFont
from .dependencies import reader

MIMES={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.txt':'text/plain'}
class DocumentError(ValueError):
    def __init__(self,category='document_validation_error',message='Use a valid PNG, JPEG, PDF, DOCX or UTF-8 TXT within the document limits.'):
        self.category=category;super().__init__(message)

def text_preview(text):
    canvas=Image.new('RGB',(1100,1500),'white');draw=ImageDraw.Draw(canvas)
    font=ImageFont.load_default(size=18)
    for candidate in ('C:/Windows/Fonts/nirmala.ttf','DejaVuSans.ttf'):
        try:font=ImageFont.truetype(candidate,18);break
        except OSError:pass
    lines=['Document text preview (first portion only)','All validated text is supplied directly for extraction.','']
    for line in text.splitlines():lines.extend(line[i:i+85] for i in range(0,max(1,len(line)),85))
    for index,line in enumerate(lines[:65]):draw.text((24,24+index*22),line,fill='black',font=font)
    output=BytesIO();canvas.save(output,format='PNG');return output.getvalue()

def decode_text(data):
    if len(data)>256*1024:raise DocumentError('document_limit','Text must not exceed 256 KiB.')
    try:text=data.decode('utf-8-sig')
    except UnicodeError:raise DocumentError('document_validation_error','TXT must use valid UTF-8 encoding.') from None
    if not text.strip() or any(ord(c)<32 and c not in '\n\r\t' for c in text):raise DocumentError('document_validation_error','The document is blank or contains unsupported binary text.')
    return text

def docx_text(data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries=archive.infolist();names=[v.filename for v in entries]
            if len(entries)>200 or len(names)!=len(set(names)) or sum(v.file_size for v in entries)>8*1024*1024:raise DocumentError('document_limit','DOCX decompressed content exceeds the safe limits.')
            for entry in entries:
                path=PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename or entry.flag_bits&1 or entry.file_size>2*1024*1024 or entry.file_size>max(1,entry.compress_size)*1000:raise DocumentError()
                if 'vbaproject' in entry.filename.casefold() or '/embeddings/' in entry.filename.casefold() or '/activex/' in entry.filename.casefold():raise DocumentError('document_validation_error','Macro or embedded-object documents are not supported.')
            if '[Content_Types].xml' not in names or 'word/document.xml' not in names:raise DocumentError()
            content=XML.fromstring(archive.read('[Content_Types].xml'),forbid_dtd=True)
            main=[v.attrib.get('ContentType') for v in content if v.attrib.get('PartName')=='/word/document.xml']
            if main!=['application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml']:raise DocumentError()
            root=XML.fromstring(archive.read('word/document.xml'),forbid_dtd=True)
            W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            body=root.find(W+'body')
            if body is None or sum(1 for _ in root.iter())>20000:raise DocumentError('document_limit','DOCX XML exceeds the safe limits.')
            # Paragraphs are visited in body/table/row/cell document order.
            lines=[]
            for paragraph in body.iter(W+'p'):
                chunks=[]
                for node in paragraph.iter():
                    if node.tag==W+'t':chunks.append(node.text or '')
                    elif node.tag==W+'tab':chunks.append('\t')
                    elif node.tag in (W+'br',W+'cr'):chunks.append('\n')
                lines.append(''.join(chunks))
            return decode_text('\n'.join(lines).encode('utf8'))
    except DocumentError:raise
    except (BadZipFile,ValueError,KeyError,RuntimeError,XML.ParseError):raise DocumentError() from None
    except Exception:raise DocumentError() from None

def prepare(data,mime,filename=''):
    if not data or len(data)>reader.MAX_IMAGE_BYTES:raise DocumentError('document_limit','Files must be nonempty and no larger than 10 MiB.')
    suffix=Path(filename).suffix.casefold() if filename else ''
    detected='image/png' if data.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if data.startswith(b'\xff\xd8\xff') else 'application/pdf' if data.startswith(b'%PDF-') else MIMES['.docx'] if data.startswith(b'PK\x03\x04') else 'text/plain'
    if suffix and (suffix not in MIMES or MIMES[suffix]!=detected):raise DocumentError()
    if mime not in (detected,'application/octet-stream',''):
        if mime.startswith('image/'):raise reader.ImageInputError('Invalid image content.')
        raise DocumentError()
    if detected.startswith('image/'):
        reader._validate_image(data)
        return data,None
    pages=[];text=None
    if detected=='application/pdf':
        if b'%%EOF' not in data[-2048:]:raise DocumentError('document_validation_error','The PDF is corrupt or incomplete.')
        process=subprocess.Popen([sys.executable,'-m','api.document_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=str(Path(__file__).resolve().parent.parent))
        try:output,_=process.communicate(data,timeout=15)
        except subprocess.TimeoutExpired:
            process.kill();process.communicate();raise DocumentError('document_timeout','PDF rendering exceeded the 15-second limit.') from None
        try:
            if process.returncode or len(output)>32*1024*1024:raise ValueError
            result=json.loads(output)
            if result.get('error')=='page_limit':raise DocumentError('document_limit','PDF supports at most 3 pages; no pages were silently omitted.')
            if result.get('error')=='encrypted_pdf':raise DocumentError('document_validation_error','Encrypted PDFs are not supported.')
            if not isinstance(result.get('pages'),list) or not 1<=len(result['pages'])<=3:raise ValueError
            pages=[base64.b64decode(v,validate=True) for v in result['pages']]
            for page in pages:reader._validate_image(page)
        except DocumentError:raise
        except Exception:raise DocumentError('document_validation_error','The PDF could not be rendered safely.') from None
    else:text=docx_text(data) if detected==MIMES['.docx'] else decode_text(data)
    preview=pages[0] if pages else text_preview(text)
    source={'text':text,'pages':tuple(pages),'preview_sha256':hashlib.sha256(preview).hexdigest(),
        'metadata':{'kind':detected,'filename':filename or 'prescription','source_sha256':hashlib.sha256(data).hexdigest(),
                    'page_count':len(pages) if pages else None,'text_characters':len(text) if text else 0,'source_bytes':len(data)}}
    return preview,source
