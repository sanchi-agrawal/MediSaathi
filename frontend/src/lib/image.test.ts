import { describe, expect, it } from 'vitest'
import { detectImageType, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, validateImageMetadata } from './image'
import { aiClient, authClient } from './api'

describe('image validation boundaries from reader.py',()=>{
  it('accepts exact byte and pixel limits',()=>{
    expect(()=>validateImageMetadata(MAX_IMAGE_BYTES,4000,2000)).not.toThrow()
    expect(4000*2000).toBe(MAX_IMAGE_PIXELS)
  })
  it('rejects oversized images and empty images',()=>{
    expect(()=>validateImageMetadata(MAX_IMAGE_BYTES+1,10,10)).toThrow('10 MiB')
    expect(()=>validateImageMetadata(0,10,10)).toThrow('empty')
    expect(()=>validateImageMetadata(100,4001,2000)).toThrow('million pixels')
    expect(()=>validateImageMetadata(100,0,2000)).toThrow()
  })
  it('checks bytes rather than trusting extensions',()=>{
    expect(detectImageType(new Uint8Array([137,80,78,71,13,10,26,10]))).toBe('image/png')
    expect(detectImageType(new Uint8Array([255,216,255,224]))).toBe('image/jpeg')
    expect(detectImageType(new Uint8Array([71,73,70,56]))).toBeNull()
    expect(detectImageType(new Uint8Array())).toBeNull()
  })
})
describe('disconnected service boundaries',()=>{
  it('cannot produce fake extraction or confirmation success',async()=>{
    expect(aiClient.connected).toBe(false)
    await expect(aiClient.confirm('medicines','example')).rejects.toThrow('not connected')
    await expect(aiClient.explain('hi','example')).rejects.toThrow('No AI request was sent')
  })
  it('cannot create an authenticated session',async()=>{
    expect(authClient.connected).toBe(false)
    await expect(authClient.signIn('example@example.com','test-only')).rejects.toThrow('not connected')
  })
})
