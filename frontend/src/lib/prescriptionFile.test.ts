import { expect,it } from 'vitest'
import { validatePrescriptionFile } from './prescriptionFile'
it('accepts UTF-8 Hindi, PDF and DOCX signatures for authoritative server validation',async()=>{
 for(const file of [new File(['Dolo सुबह 1 tablet'],'a.txt',{type:'text/plain'}),new File(['%PDF-1.7\n'],'a.pdf',{type:'application/pdf'}),new File([new Uint8Array([80,75,3,4])],'a.docx')])expect(await validatePrescriptionFile(file)).toBeNull()
})
it('rejects renamed, empty, oversized, invalid UTF-8 and unsupported documents',async()=>{
 for(const file of [new File(['bad'],'a.pdf'),new File(['bad'],'a.docx'),new File([''],'a.txt'),new File(['  '],'a.txt'),new File([new Uint8Array([255])],'a.txt'),new File(['x'.repeat(262145)],'a.txt'),new File(['x'],'a.exe')])await expect(validatePrescriptionFile(file)).rejects.toThrow()
})
