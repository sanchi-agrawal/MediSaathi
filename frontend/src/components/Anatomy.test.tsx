// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import * as T from 'three'
import Anatomy from './Anatomy'
import { restingPose } from './anatomyAppearance'
import { setLanguage } from '../lib/language'

const mocks = vi.hoisted(() => ({
  load: vi.fn(), reduced: false, frames: [] as FrameRequestCallback[], render: vi.fn(), intersect: vi.fn(() => [] as {object: import('three').Object3D}[]),
  visibility: undefined as ((entries: { isIntersecting: boolean }[]) => void) | undefined,
}))
vi.mock('three', async original => {
  const actual = await original<typeof import('three')>()
  return { ...actual,
    WebGLRenderer: class {
      domElement = document.createElement('canvas')
      setPixelRatio() {} setSize() {} dispose() {} render = mocks.render
    },
    PMREMGenerator: class { fromScene() { return { texture: new actual.Texture(), dispose() {} } } dispose() {} },
    Raycaster: class { setFromCamera() {} intersectObjects = mocks.intersect },
  }
})
vi.mock('three/addons/loaders/GLTFLoader.js', () => ({ GLTFLoader: class { setDRACOLoader() { return this } loadAsync = mocks.load } }))
vi.mock('three/addons/loaders/DRACOLoader.js', () => ({ DRACOLoader: class { setDecoderPath() { return this } setDecoderConfig() { return this } dispose() {} } }))

function fixture(names: string[]) {
  const root = new T.Group()
  names.forEach(name => {
    const geometry = new T.BufferGeometry()
    geometry.setAttribute('position', new T.Float32BufferAttribute(name.startsWith('skin') ? [-1.3,2,.1,1.3,2,.1,0,3.18,.5,0,-3.5,.4] : name === 'brain__FMA61830' ? [-.27,2.69,.02,.27,3.14,.7] : [-.5,-.13,.1,.5,2.1,.8],3))
    const mesh = new T.Mesh(geometry, new T.MeshStandardMaterial()); mesh.name = name; root.add(mesh)
  })
  return { scene: root }
}
function tick() { mocks.frames.shift()?.(0) }
function stage() {
  const element = screen.getByRole('img')
  element.getBoundingClientRect = () => ({ left: 0, top: 0, right: 600, bottom: 400, width: 600, height: 400, x: 0, y: 0, toJSON() {} })
  element.setPointerCapture = vi.fn(); element.hasPointerCapture = () => true; element.releasePointerCapture = vi.fn()
  return element
}
function pointer(element: HTMLElement, type: string, values: object = {}) {
  fireEvent(element, Object.assign(new Event(type), { pointerType: 'mouse', pointerId: 1, button: 0, clientX: 300, clientY: 200, ...values }))
}

beforeEach(() => {
  mocks.reduced = false; mocks.frames = []; mocks.render.mockClear(); mocks.load.mockReset()
  mocks.intersect.mockReturnValue([])
  vi.stubGlobal('devicePixelRatio', 1)
  vi.stubGlobal('matchMedia', () => ({ get matches() { return mocks.reduced }, addEventListener() {}, removeEventListener() {} }))
  vi.stubGlobal('IntersectionObserver', class { constructor(callback: typeof mocks.visibility) { mocks.visibility = callback } observe() {} disconnect() {} })
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  vi.stubGlobal('requestAnimationFrame', (fn: FrameRequestCallback) => { mocks.frames.push(fn); return mocks.frames.length })
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  mocks.load.mockImplementation(async (url: string) => url.includes('cerebrum') ? fixture(['brain__FMA61830']) : url.includes('skin') ? fixture(['skin__FMA7163']) : fixture(['heart__FMA7274', 'lungs__FMA7333', 'liver__FMA7197', 'stomach__FMA7148', 'kidneys__FMA7204', 'intestines__FMA7207', 'brain__FMA67944']))
  setLanguage('en')
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); setLanguage('en') })

it('loads matching assets, enables only supported organs, and preserves keyboard selection in Hindi', async () => {
  render(<Anatomy/>); await screen.findByRole('button', { name: 'Kidneys' })
  expect(mocks.load).toHaveBeenCalledWith('/models/anatomy-organs.glb')
  expect(mocks.load).toHaveBeenCalledWith('/models/anatomy-skin.glb')
  expect(mocks.load).toHaveBeenCalledWith('/models/anatomy-cerebrum.glb')
  expect(screen.getByRole('button', { name: 'Brain' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Kidneys' }))
  expect(screen.getByText('Filter blood and regulate water and salts.')).toBeTruthy()
  setLanguage('hi'); const button = await screen.findByRole('button', { name: 'हृदय' })
  button.focus(); await userEvent.keyboard('{Enter}')
  expect(button.getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByText('शरीर में रक्त का संचार करता है।')).toBeTruthy()
  expect(screen.queryByRole('slider')).toBeNull()
})

it('keeps the enlarged controls and rotation instructions accessible in both languages',async()=>{
  render(<Anatomy/>);await screen.findByRole('button',{name:'Brain'})
  expect(screen.getByRole('region',{name:'Anatomy controls'})).toBeTruthy()
  expect(screen.getByText('Move your pointer to rotate. Drag to explore.')).toBeTruthy()
  expect(screen.getByRole('button',{name:'Reset view'})).toBeTruthy()
  setLanguage('hi')
  expect(await screen.findByRole('region',{name:'शरीर रचना के नियंत्रण'})).toBeTruthy()
  expect(screen.getByText('घुमाने के लिए पॉइंटर चलाएँ। अधिक देखने के लिए खींचें।')).toBeTruthy()
  expect(screen.getByRole('button',{name:'दृश्य रीसेट करें'})).toBeTruthy()
  expect(screen.queryByRole('slider')).toBeNull()
})

it('keeps skin and organ roots in exactly one source frame and uses translucent PBR skin', async () => {
  render(<Anatomy/>); await screen.findByRole('button', { name: 'Heart' }); tick()
  const scene = mocks.render.mock.calls.at(-1)![0] as T.Scene
  const skin = scene.getObjectByName('skin__FMA7163') as T.Mesh
  const heart = scene.getObjectByName('heart__FMA7274') as T.Mesh
  expect(skin.parent?.parent).toBe(heart.parent?.parent)
  expect(skin.parent?.parent?.position.y).toBeLessThan(-1)
  expect(skin.parent?.position.toArray()).toEqual([0, 0, 0])
  expect(heart.parent?.scale.toArray()).toEqual([1, 1, 1])
  const material = skin.material as T.MeshPhysicalMaterial
  expect(material.isMeshPhysicalMaterial).toBe(true); expect(material.transparent).toBe(true)
  expect(material.depthWrite).toBe(false); expect(material.opacity).toBeLessThan(.25)
  expect(material.side).toBe(T.DoubleSide); expect(material.opacity).toBeGreaterThanOrEqual(.08)
  expect(skin.visible).toBe(true); expect(skin.renderOrder).toBe(0)
  expect(document.querySelector('[data-shell-state="loaded"]')).toBeTruthy()
  expect(scene.environment).toBeTruthy()
  expect(scene.children.filter(child => child instanceof T.DirectionalLight)).toHaveLength(3)
})

it('shows a static fallback with no organ controls when the organ asset fails', async () => {
  mocks.load.mockRejectedValue(new Error('missing model')); render(<Anatomy/>)
  await screen.findByText('3D unavailable. Please reload to try again.')
  expect(screen.queryByRole('button', { name: 'Heart' })).toBeNull()
})

it('keeps original organs and reports a failed shell instead of inventing an outline', async () => {
  const implementation = mocks.load.getMockImplementation()!
  mocks.load.mockImplementation((url: string) => url.includes('skin') ? Promise.reject(new Error('missing shell')) : implementation(url))
  render(<Anatomy/>); await screen.findByText('Body outline unavailable. Showing original organs.')
  expect(screen.getByRole('button', { name: 'Heart' })).toBeTruthy()
})

it('reuses the original brain parts and supports real cortex hover/click and Hindi cards', async()=>{
  render(<Anatomy/>);await screen.findByRole('button',{name:'Brain'});tick()
  const scene=mocks.render.mock.calls.at(-1)![0] as T.Scene
  const cortex=scene.getObjectByName('brain__FMA61830') as T.Mesh
  const cerebellum=scene.getObjectByName('brain__FMA67944') as T.Mesh
  const skin=scene.getObjectByName('skin__FMA7163') as T.Mesh
  expect(cerebellum.visible).toBe(true);expect(cortex.visible).toBe(true)
  expect(cortex.parent?.parent).toBe(skin.parent?.parent)
  expect(cortex.parent?.position.toArray()).toEqual([0,0,0])
  expect(cortex.parent?.scale.toArray()).toEqual([1,1,1])
  const element=stage();mocks.intersect.mockReturnValue([{object:cortex}])
  pointer(element,'pointermove');tick()
  expect(screen.getByRole('button',{name:'Brain'}).getAttribute('aria-pressed')).toBe('false')
  expect((cortex.material as T.MeshPhysicalMaterial).emissive.getHex()).not.toBe(0)
  pointer(element,'pointerdown');pointer(element,'pointerup');tick()
  expect(screen.getByRole('button',{name:'Brain'}).getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByText('Coordinates thought, movement and many body functions.')).toBeTruthy()
  setLanguage('hi');expect(await screen.findByRole('button',{name:'मस्तिष्क'})).toBeTruthy()
  expect(screen.getByText('सोचने, चलने और शरीर के कई कार्यों का समन्वय करता है।')).toBeTruthy()
})

it('does not expose the partial brain as a full brain when the cortex fails to load', async()=>{
  const implementation=mocks.load.getMockImplementation()!
  mocks.load.mockImplementation((url:string)=>url.includes('cerebrum')?Promise.reject(new Error('missing cortex')):implementation(url))
  render(<Anatomy/>);await screen.findByText('Brain unavailable. Other organs remain available.');tick()
  expect(screen.queryByRole('button',{name:'Brain'})).toBeNull()
  expect(screen.getByRole('button',{name:'Heart'})).toBeTruthy()
  const scene=mocks.render.mock.calls.at(-1)![0] as T.Scene
  expect(scene.getObjectByName('brain__FMA67944')?.visible).toBe(false)
})

it('rotates from pointer movement, resets after exit, and pauses offscreen', async () => {
  render(<Anatomy/>); await screen.findByRole('button', { name: 'Heart' }); tick()
  const element = stage(), scene = mocks.render.mock.calls.at(-1)![0] as T.Scene
  const body = scene.children.find(child => child instanceof T.Group)!
  pointer(element, 'pointermove', { clientX: 590, clientY: 250 }); tick()
  expect(body.rotation.y).toBeGreaterThan(restingPose.yaw)
  pointer(element, 'pointerleave'); for (let i = 0; i < 60; i++) tick()
  expect(body.rotation.y).toBeCloseTo(restingPose.yaw, 2)
  mocks.visibility?.([{ isIntersecting: false }]); const count = mocks.render.mock.calls.length
  pointer(element, 'pointermove', { clientX: 100 }); tick()
  expect(mocks.render).toHaveBeenCalledTimes(count)
})

it('keeps deliberate touch rotation bounded and reduced-motion hover still', async () => {
  mocks.reduced = true; render(<Anatomy/>); await screen.findByRole('button', { name: 'Heart' }); tick()
  const element = stage(), scene = mocks.render.mock.calls.at(-1)![0] as T.Scene
  const body = scene.children.find(child => child instanceof T.Group)!
  pointer(element, 'pointermove', { clientX: 590 }); tick()
  expect(body.rotation.y).toBe(restingPose.yaw)
  pointer(element, 'pointerdown', { pointerType: 'touch' })
  pointer(element, 'pointermove', { pointerType: 'touch', clientX: 9999, clientY: 9999 }); tick()
  expect(body.rotation.y).toBeCloseTo(.95); expect(body.rotation.x).toBeCloseTo(.2)
  pointer(element, 'pointerup', { pointerType: 'touch' }); tick()
  expect(body.rotation.y).toBeCloseTo(restingPose.yaw)
  expect(mocks.frames).toHaveLength(0)
})
