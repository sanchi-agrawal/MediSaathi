// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,render,screen} from '@testing-library/react'
import OfflineDemoNotice from './OfflineDemoNotice'
import {setLanguage} from '../lib/language'

afterEach(()=>{cleanup();setLanguage('en');vi.unstubAllEnvs()})

it('labels the public deployment as fictional-data-only in English and Hindi',()=>{
 vi.stubEnv('VITE_MEDISAATHI_PREVIEW','1')
 render(<OfflineDemoNotice/>)
 expect(screen.getByRole('status').textContent).toContain('Public preview: use fictional information only.')
 act(()=>setLanguage('hi'))
 expect(screen.getByRole('status').textContent).toContain('केवल काल्पनिक जानकारी')
})
