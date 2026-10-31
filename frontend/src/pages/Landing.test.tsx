// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Landing from './Landing'
import Anatomy from '../components/Anatomy'
import { setLanguage } from '../lib/language'
vi.mock('three',async original=>({...await original<typeof import('three')>(),WebGLRenderer:class {constructor(){throw new Error('WebGL unavailable')}}}))
afterEach(()=>{cleanup();setLanguage('en');localStorage.clear()})
it('switches the full landing page and stores preference across remounts',async()=>{
 render(<MemoryRouter><Landing/></MemoryRouter>);fireEvent.click(screen.getByRole('button',{name:'हिंदी'}))
 expect(screen.getByRole('heading',{level:1}).textContent).toContain('अपनी दवाइयों को बेहतर समझें।')
 expect(screen.getByText('प्रिस्क्रिप्शन विश्लेषण')).toBeTruthy()
 expect(localStorage.getItem('medisaathi.interface-language')).toBe('hi')
 cleanup();render(<MemoryRouter><Landing/></MemoryRouter>);expect(screen.getByRole('button',{name:'हिंदी'}).getAttribute('aria-pressed')).toBe('true')
 fireEvent.click(screen.getByRole('button',{name:'English'}));expect(screen.getByText('Prescription analysis')).toBeTruthy()
})
it('retains accessible translated organ exploration without WebGL and has no slider',()=>{
 setLanguage('hi');render(<Anatomy/>);expect(screen.getByText('3D उपलब्ध नहीं है। फिर से कोशिश करने के लिए पेज दोबारा लोड करें।')).toBeTruthy()
 expect(screen.queryByRole('button',{name:'गुर्दे'})).toBeNull()
 expect(screen.queryByRole('button',{name:'मस्तिष्क'})).toBeNull()
 expect(screen.queryByRole('slider')).toBeNull()
 expect(screen.getAllByRole('button').length).toBe(1)
})
it('preserves landing navigation destinations',()=>{render(<MemoryRouter><Landing/></MemoryRouter>);expect(screen.getByText('Sign in').closest('a')?.getAttribute('href')).toBe('/login');expect(screen.getByText('Start with your prescription').closest('a')?.getAttribute('href')).toBe('/dashboard/analysis');expect(screen.getAllByText('Explore dashboard')[0].closest('a')?.getAttribute('href')).toBe('/dashboard')})
it('restores Hindi from storage on a fresh module load',async()=>{localStorage.setItem('medisaathi.interface-language','hi');vi.resetModules();const fresh=await import('../lib/language');const {result,unmount}=renderHook(()=>fresh.useLanguage());expect(result.current.language).toBe('hi');expect(document.documentElement.lang).toBe('hi');unmount();fresh.setLanguage('en')})
