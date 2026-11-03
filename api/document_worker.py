"""Bounded PDF renderer subprocess. Never executes PDF scripts or fetches links."""
import base64,json,math,sys

def limit_memory():
    ceiling=512*1024*1024
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes as W
        class Basic(ctypes.Structure):
            _fields_=[('ProcessTime',ctypes.c_longlong),('JobTime',ctypes.c_longlong),('Flags',W.DWORD),('MinWorking',ctypes.c_size_t),('MaxWorking',ctypes.c_size_t),('Active',W.DWORD),('Affinity',ctypes.c_size_t),('Priority',W.DWORD),('Scheduling',W.DWORD)]
        class IO(ctypes.Structure):_fields_=[(name,ctypes.c_ulonglong) for name in ['ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes']]
        class Extended(ctypes.Structure):_fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];kernel.CreateJobObjectW.restype=W.HANDLE
        kernel.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD]
        kernel.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];kernel.GetCurrentProcess.restype=W.HANDLE
        job=kernel.CreateJobObjectW(None,None);info=Extended();info.Basic.Flags=0x100;info.ProcessMemory=ceiling
        if not job or not kernel.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)) or not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):raise RuntimeError('Memory limit unavailable')
        # Retain until process exit; Windows closes the handle on termination.
        globals()['_JOB']=job
    else:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(ceiling,ceiling))

def run():
    limit_memory()
    import pymupdf
    data=sys.stdin.buffer.read(10*1024*1024+1)
    if len(data)>10*1024*1024:raise ValueError
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        if doc.needs_pass or doc.is_encrypted or doc.metadata.get('encryption'):return {'error':'encrypted_pdf'}
        if doc.is_repaired:return {'error':'invalid_pdf'}
        if not 1<=len(doc)<=3:return {'error':'page_limit'}
        pages=[]
        for page in doc:
            width,height=page.rect.width,page.rect.height
            if not all(math.isfinite(v) and 0<v<=20000 for v in (width,height)):raise ValueError
            scale=min(2,math.sqrt(1_900_000/(width*height)))
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),colorspace=pymupdf.csRGB,alpha=False)
            if pix.width*pix.height>2_000_000:raise ValueError
            pages.append(base64.b64encode(pix.tobytes('png')).decode('ascii'))
        return {'pages':pages}
if __name__=='__main__':
    try:result=run()
    except Exception:result={'error':'invalid_pdf'}
    sys.stdout.write(json.dumps(result))
