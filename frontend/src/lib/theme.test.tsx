// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { act,cleanup,renderHook } from '@testing-library/react'
import fs from 'node:fs'
import path from 'node:path'
import { setTheme,useTheme } from './theme'
afterEach(()=>{cleanup();setTheme('dark');localStorage.removeItem('medisaathi.appearance')})
it('updates the root shared by every page and persists the preference across fresh module loading',async()=>{
  const hook=renderHook(()=>useTheme());act(()=>setTheme('light'));expect(hook.result.current.theme).toBe('light');expect(document.documentElement.dataset.theme).toBe('light');expect(localStorage.getItem('medisaathi.appearance')).toBe('light');hook.unmount()
  vi.resetModules();const fresh=await import('./theme');const restored=renderHook(()=>fresh.useTheme());expect(restored.result.current.theme).toBe('light');restored.unmount();fresh.setTheme('dark')
})
it('uses central color tokens in every application stylesheet, including auth, reviews, schedules and dialogs',()=>{
  const files=fs.readdirSync(path.resolve('src')).filter(f=>f.endsWith('.css')&&!['theme-tokens.css'].includes(f))
  for(const file of files){const css=fs.readFileSync(path.resolve('src',file),'utf8');expect(css.match(/#[\da-fA-F]{3,8}\b/g),file).toBeNull()}
  const palette=fs.readFileSync(path.resolve('src/theme-tokens.css'),'utf8')
  for(const color of ['#FCFAFF','#FFFFFF','#F3EEFF','#7C3AED','#5B21B6','#C4B5FD','#221535','#6B6080','#E9DDF8'])expect(palette).toContain(color)
  expect(palette).toContain('.auth-image-panel');expect(palette).toContain('--dark-tone-')
  const css=fs.readFileSync(path.resolve('src/theme.css'),'utf8');for(const selector of ['.sidebar','.dashboard-topbar','.panel','textarea','.error-message','.badge-green','table'])expect(css).toContain(selector)
})
it('applies stored theme before application startup and supports reduced motion',()=>{
  const html=fs.readFileSync(path.resolve('index.html'),'utf8');expect(html.indexOf('medisaathi.appearance')).toBeLessThan(html.indexOf('src/main.tsx'))
  expect(fs.readFileSync(path.resolve('src/theme.css'),'utf8')).toContain('prefers-reduced-motion:reduce')
})
it('uses readable light text and interactive contrast instead of pale lavender text',()=>{
  function luminance(hex:string){const c=hex.match(/[\da-f]{2}/gi)!.map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722}
  function ratio(a:string,b:string){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
  for(const color of ['#221535','#6B6080','#7C3AED','#5B21B6','#B42332','#176746','#8A4B08'])expect(ratio(color,'#FFFFFF'),color).toBeGreaterThanOrEqual(4.5)
  expect(ratio('#6B6080','#F3EEFF')).toBeGreaterThanOrEqual(4.5)
})
