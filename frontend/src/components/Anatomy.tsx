import { useEffect, useRef, useState } from 'react'
import * as T from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { MousePointer2, RotateCcw } from 'lucide-react'
import { useLanguage } from '../lib/language'
import { AnatomyFallback } from './AnatomyFallback'
import { fitCamera, measureUpperBody, organMaterial, restingPose, rotationLimits, shellMaterial, updateSelection, updateShellSelection } from './anatomyAppearance'

export const organs = [
  ['Brain', 'Coordinates thought, movement and many body functions.'],
  ['Heart', 'Pumps blood throughout the body.'],
  ['Lungs', 'Exchange oxygen and carbon dioxide during breathing.'],
  ['Liver', 'Processes nutrients and helps remove substances from blood.'],
  ['Stomach', 'Mixes food with acid and enzymes for digestion.'],
  ['Kidneys', 'Filter blood and regulate water and salts.'],
  ['Intestines', 'Absorb nutrients and water and move digestive waste.'],
] as const

function disposeTree(root: T.Object3D) {
  const geometries = new Set<T.BufferGeometry>(), materials = new Set<T.Material>()
  root.traverse(object => {
    if (object instanceof T.Mesh) {
      geometries.add(object.geometry)
      const list = Array.isArray(object.material) ? object.material : [object.material]
      list.forEach(material => materials.add(material))
    }
  })
  geometries.forEach(geometry => geometry.dispose())
  materials.forEach(material => material.dispose())
}

export default function Anatomy() {
  const { t } = useLanguage()
  const host = useRef<HTMLDivElement>(null), selection = useRef(1), reset = useRef(() => {})
  const [selected, setSelected] = useState(1), [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(true), [available, setAvailable] = useState<number[]>([])
  const [shellMissing, setShellMissing] = useState(false)
  const [brainMissing, setBrainMissing] = useState(false)
  selection.current = selected

  useEffect(() => {
    const element = host.current!
    let renderer: T.WebGLRenderer
    try { renderer = new T.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' }) }
    catch { setFailed(true); setLoading(false); return }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
    renderer.outputColorSpace = T.SRGBColorSpace
    renderer.toneMapping = T.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    element.appendChild(renderer.domElement)

    const scene = new T.Scene(), body = new T.Group(), content = new T.Group()
    const camera = new T.PerspectiveCamera(34, 1, .1, 60), meshes: T.Mesh[] = [], shells: T.Mesh[] = []
    const brainParts: T.Mesh[] = [], cortex: T.Mesh[] = []
    body.add(content); scene.add(body)
    body.rotation.set(restingPose.pitch, restingPose.yaw, 0)
    scene.add(new T.HemisphereLight('#b9cbdc', '#283043', .55))
    const key = new T.DirectionalLight('#fff1e7', 2.6); key.position.set(-3, 4, 6)
    const rim = new T.DirectionalLight('#64d5ed', 1.7); rim.position.set(3, 2, -4)
    const fill = new T.DirectionalLight('#b3c9dd', .65); fill.position.set(4, 0, 4)
    scene.add(key, rim, fill)

    // Small, generated studio reflection map: no HDR download or postprocessing.
    let environment: T.WebGLRenderTarget | undefined
    const studio = new RoomEnvironment(), pmrem = new T.PMREMGenerator(renderer)
    try { environment = pmrem.fromScene(studio, .04, .1, 30, { size: 128 }); scene.environment = environment.texture }
    catch { /* Direct key/rim/fill remain usable if the environment cannot be allocated. */ }
    finally { studio.dispose(); pmrem.dispose() }

    let disposed = false, x = restingPose.pitch, y = restingPose.yaw, hover = -1, frame = 0
    let framingBounds: T.Box3 | null = null
    let viewportWidth = 0, viewportHeight = 0
    let visible = true, dragging = false, pointerId: number | null = null, moved = false
    let lastX = 0, lastY = 0, startX = 0, startY = 0
    const motion = matchMedia('(prefers-reduced-motion: reduce)')
    const raycaster = new T.Raycaster(), pointer = new T.Vector2()

    function draw() {
      frame = 0
      if (disposed || !visible || document.hidden) return
      const damping = motion.matches ? 1 : .12
      body.rotation.x += (x - body.rotation.x) * damping
      body.rotation.y += (y - body.rotation.y) * damping
      if (framingBounds && viewportWidth && viewportHeight) fitCamera(camera, viewportWidth, viewportHeight, framingBounds, { pitch: body.rotation.x, yaw: body.rotation.y })
      updateSelection(meshes, selection.current, hover)
      updateShellSelection(shells, selection.current, hover)
      renderer.render(scene, camera)
      if (Math.abs(x - body.rotation.x) + Math.abs(y - body.rotation.y) > .001) wake()
    }
    function wake() { if (!frame && !disposed && visible && !document.hidden) frame = requestAnimationFrame(draw) }
    function pick(event: PointerEvent, commit = false) {
      const rect = element.getBoundingClientRect()
      if (!rect.width || !rect.height) return
      pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1)
      // Keep raycasting correct even if a pointer event arrives before the next frame.
      scene.updateMatrixWorld(true); camera.updateMatrixWorld(true)
      raycaster.setFromCamera(pointer, camera)
      const hit = raycaster.intersectObjects(meshes, false)[0]
      hover = hit?.object.userData.organ ?? -1
      if (hit && commit) setSelected(hit.object.userData.organ)
      element.style.cursor = dragging ? 'grabbing' : hit ? 'pointer' : 'grab'
    }
    function move(event: PointerEvent) {
      if (dragging) {
        if (event.pointerId !== pointerId) return
        moved ||= Math.hypot(event.clientX - startX, event.clientY - startY) > 5
        y += (event.clientX - lastX) * .008; x += (event.clientY - lastY) * .004
        lastX = event.clientX; lastY = event.clientY
      } else if (event.pointerType === 'mouse') {
        pick(event)
        if (!motion.matches) {
          const rect = element.getBoundingClientRect()
          if (rect.width && rect.height) {
            y = restingPose.yaw + ((event.clientX - rect.left) / rect.width - .5) * .6
            x = restingPose.pitch + ((event.clientY - rect.top) / rect.height - .5) * .18
          }
        }
      }
      x = T.MathUtils.clamp(x, ...rotationLimits.pitch); y = T.MathUtils.clamp(y, ...rotationLimits.yaw)
      wake()
    }
    function down(event: PointerEvent) {
      if (dragging || (event.pointerType === 'mouse' && event.button !== 0)) return
      dragging = true; moved = false; pointerId = event.pointerId
      startX = lastX = event.clientX; startY = lastY = event.clientY
      element.setPointerCapture(event.pointerId); element.style.cursor = 'grabbing'
    }
    function rest() { hover = -1; x = restingPose.pitch; y = restingPose.yaw; wake() }
    function up(event: PointerEvent) {
      if (event.pointerId !== pointerId) return
      if (!moved) pick(event, true)
      dragging = false; pointerId = null
      if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId)
      element.style.cursor = 'grab'
      const rect = element.getBoundingClientRect()
      if (event.pointerType === 'touch' || event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) rest()
      wake()
    }
    function leave() { if (!dragging) rest() }
    function cancel() { dragging = false; pointerId = null; rest() }
    function lostCapture() { if (dragging) cancel() }
    function resize() {
      const rect = element.getBoundingClientRect()
      if (!rect.width || !rect.height) return
      viewportWidth = rect.width; viewportHeight = rect.height
      renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5, Math.sqrt(1_600_000 / (rect.width * rect.height))))
      renderer.setSize(rect.width, rect.height)
      if (framingBounds) fitCamera(camera, rect.width, rect.height, framingBounds, { pitch: body.rotation.x, yaw: body.rotation.y })
      wake()
    }
    function lost(event: Event) { event.preventDefault(); setFailed(true); cancelAnimationFrame(frame); frame = 0 }
    function pageVisibility() { if (document.hidden) { cancelAnimationFrame(frame); frame = 0 } else wake() }

    const decoder = new DRACOLoader().setDecoderPath('/draco/').setDecoderConfig({ type: 'wasm' })
    const loader = new GLTFLoader().setDRACOLoader(decoder)
    const organLoad = loader.loadAsync('/models/anatomy-organs.glb').then(gltf => {
      if (disposed) { disposeTree(gltf.scene); return }
      gltf.scene.traverse(object => {
        if (!(object instanceof T.Mesh)) return
        const id = organs.findIndex(([name]) => object.name.startsWith(name.toLowerCase() + '__FMA'))
        if (id < 0) { object.visible = false; return }
        object.userData.organ = id
        const previous = Array.isArray(object.material) ? object.material : [object.material]
        previous.forEach(material => material.dispose())
        object.material = organMaterial(id)
        // Reuse the supplied cerebellum and brainstem, but only expose Brain
        // after the corresponding real cerebral cortex also loads.
        if (id === 0) { object.visible = false; brainParts.push(object) }
        else meshes.push(object)
      })
      if (!meshes.length) { disposeTree(gltf.scene); throw new Error('No supported organ geometry') }
      content.add(gltf.scene)
      wake()
    })
    const brainLoad = loader.loadAsync('/models/anatomy-cerebrum.glb').then(gltf => {
      if (disposed) { disposeTree(gltf.scene); return }
      gltf.scene.traverse(object => {
        if (!(object instanceof T.Mesh)) return
        if (object.name !== 'brain__FMA61830') { object.visible = false; return }
        const previous = Array.isArray(object.material) ? object.material : [object.material]
        previous.forEach(material => material.dispose())
        object.material = organMaterial(0); object.userData.organ = 0
        object.visible = false; cortex.push(object)
      })
      if (!cortex.length) { disposeTree(gltf.scene); throw new Error('Verified cerebral cortex missing') }
      // Registration is baked into the imported GLB and recorded in its source
      // manifest. No independent runtime brain scaling/positioning is applied.
      content.add(gltf.scene)
    }).catch(() => { if (!disposed) setBrainMissing(true) })
    const shellLoad = loader.loadAsync('/models/anatomy-skin.glb').then(gltf => {
      if (disposed) { disposeTree(gltf.scene); return }
      gltf.scene.traverse(object => {
        if (!(object instanceof T.Mesh)) return
        if (object.name !== 'skin__FMA7163') { object.visible = false; return }
        const previous = Array.isArray(object.material) ? object.material : [object.material]
        previous.forEach(material => material.dispose())
        object.material = shellMaterial()
        // Opaque organs write depth first; the transparent shell then uses
        // Three.js's normal depth-tested sorting instead of an overlay order.
        object.renderOrder = 0; object.visible = true; shells.push(object)
      })
      if (!shells.length) { disposeTree(gltf.scene); throw new Error('Matching skin mesh missing') }
      content.add(gltf.scene); wake()
    }).catch(() => { if (!disposed) setShellMissing(true) })
    Promise.allSettled([organLoad, shellLoad, brainLoad]).then(([organsResult]) => {
      decoder.dispose()
      if (disposed) return
      if (organsResult.status === 'rejected') { setFailed(true); setAvailable([]) }
      else {
        if (cortex.length) {
          for (const part of [...cortex, ...brainParts]) { part.visible = true; meshes.push(part) }
        }
        setAvailable([...new Set(meshes.map(mesh => mesh.userData.organ as number))])
      }
      const sourceBounds = measureUpperBody(content, meshes, shells)
      if (sourceBounds) {
        // Translate both roots together; never stretch or reposition anatomy.
        content.position.copy(sourceBounds.getCenter(new T.Vector3())).negate()
        framingBounds = sourceBounds.clone().translate(content.position)
      }
      setLoading(false); resize(); wake()
    })

    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting
      if (visible) wake(); else { cancelAnimationFrame(frame); frame = 0 }
    })
    observer.observe(element)
    const sizes = new ResizeObserver(resize); sizes.observe(element)
    const handlers = { pointermove: move, pointerdown: down, pointerup: up, pointerleave: leave, pointercancel: cancel, lostpointercapture: lostCapture }
    Object.entries(handlers).forEach(([name, fn]) => element.addEventListener(name, fn as EventListener))
    element.addEventListener('organ-change', wake)
    motion.addEventListener('change', rest)
    document.addEventListener('visibilitychange', pageVisibility)
    renderer.domElement.addEventListener('webglcontextlost', lost)
    reset.current = rest
    resize()

    return () => {
      disposed = true; cancelAnimationFrame(frame); decoder.dispose(); observer.disconnect(); sizes.disconnect()
      Object.entries(handlers).forEach(([name, fn]) => element.removeEventListener(name, fn as EventListener))
      element.removeEventListener('organ-change', wake); motion.removeEventListener('change', rest)
      document.removeEventListener('visibilitychange', pageVisibility); renderer.domElement.removeEventListener('webglcontextlost', lost)
      disposeTree(body); environment?.dispose(); renderer.dispose(); renderer.domElement.remove()
    }
  }, [])

  useEffect(() => { host.current?.dispatchEvent(new Event('organ-change')) }, [selected])
  return <div className="anatomy-explorer" aria-busy={loading} data-shell-state={loading ? 'loading' : failed ? 'unavailable' : shellMissing ? 'missing' : 'loaded'} data-brain-state={loading ? 'loading' : failed ? 'unavailable' : brainMissing ? 'missing' : 'loaded'}>
    <div className="anatomy-stage">
    <div ref={host} className="anatomy-viewport" role="img" aria-label={t('Anatomical organ model')} aria-describedby="anatomy-help" hidden={failed}/>
    {(failed || loading) && <AnatomyFallback loading={!failed}/>}
    {!loading && !failed && <div className="organ-card" aria-live="polite"><span className="organ-eyebrow">{t('Explore your anatomy')}</span><h2 className="organ-name">{t(organs[selected][0])}</h2><p>{t(organs[selected][1])}</p></div>}
    </div>
    {!loading && shellMissing && !failed && <p className="shell-notice" role="status">{t('Body outline unavailable. Showing original organs.')}</p>}
    {!loading && brainMissing && !failed && <p className="shell-notice" role="status">{t('Brain unavailable. Other organs remain available.')}</p>}
    <section className="anatomy-controls-panel" aria-label={t('Anatomy controls')}>
      <div className="organ-list" role="group" aria-label={t('Select an organ')}>{!loading && !failed && organs.map(([name], i) => available.includes(i) && <button key={name} aria-pressed={selected === i} onClick={() => setSelected(i)}>{t(name)}</button>)}</div>
      <div className="rotation-help"><span className="rotation-instruction" id="anatomy-help"><MousePointer2 size={19} aria-hidden="true"/>{t('Move your pointer to rotate. Drag to explore.')}</span><button onClick={() => reset.current()}><RotateCcw size={17} aria-hidden="true"/>{t('Reset view')}</button></div>
    </section>
    <div className="anatomy-footnote">
    <a className="model-credit" href="/models/ATTRIBUTION.txt">BodyParts3D / DBCLS / CC BY-SA 2.1 JP</a>
    <p className="education-note">{t('Educational model — not a diagnosis.')}</p>
    </div>
  </div>
}
