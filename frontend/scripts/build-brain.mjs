// Rebuild the licensed cortical GLB from the pinned STL sources. No anatomy is
// generated here: only source registration, vertex welding and simplification.
import fs from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { Document, NodeIO } from '@gltf-transform/core'
import { KHRDracoMeshCompression } from '@gltf-transform/extensions'
import { draco, join, prune, simplify, weld } from '@gltf-transform/functions'
import draco3d from 'draco3dgltf'
import { MeshoptSimplifier } from 'meshoptimizer'
import * as THREE from 'three'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'

const root = new URL('../', import.meta.url)
const manifestUrl = new URL('public/models/brain-sources.json', root)
const manifest = JSON.parse(await fs.readFile(manifestUrl, 'utf8'))
const io = new NodeIO().registerExtensions([KHRDracoMeshCompression]).registerDependencies({
  'draco3d.decoder': await draco3d.createDecoderModule(),
  'draco3d.encoder': await draco3d.createEncoderModule(),
})
await MeshoptSimplifier.ready
const existing = await io.read(new URL('public/models/anatomy-organs.glb', root).pathname.replace(/^\/(\w:)/, '$1'))
const stl = new STLLoader()
async function sourceGeometry(source) {
  const bytes = await fs.readFile(new URL(`.anatomy-work/${source.id}.stl`, root))
  const blobHash = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex')
  if (blobHash !== source.gitBlob) throw new Error(`Source hash mismatch: ${source.id}`)
  return stl.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))
}
function bounds(array) {
  const box = new THREE.Box3(), point = new THREE.Vector3()
  for (let index = 0; index < array.length; index += 3) box.expandByPoint(point.fromArray(array, index))
  return box
}
const references = await Promise.all(manifest.alignmentReferences.map(async source => {
  const geometry = await sourceGeometry(source)
  const original = bounds(geometry.getAttribute('position').array)
  const node = existing.getRoot().listNodes().find(node => node.getName().endsWith(`__${source.id}`))
  if (!node) throw new Error(`Reference not present: ${source.id}`)
  const target = bounds(node.getMesh().listPrimitives()[0].getAttribute('POSITION').getArray())
  geometry.dispose()
  return { id: source.id, original, target }
}))

// Recover one rigid axis conversion + uniform scale + translation from three
// corresponding anatomical structures. Never fit the new brain to a guessed box.
const axes = ['x', 'y', 'z'], permutations = [[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]]
let best
for (const permutation of permutations) for (const sx of [-1,1]) for (const sy of [-1,1]) for (const sz of [-1,1]) {
  const signs = [sx,sy,sz]
  let numerator = 0, denominator = 0
  for (const reference of references) for (let axis = 0; axis < 3; axis++) {
    const from = reference.original.max[axes[permutation[axis]]] - reference.original.min[axes[permutation[axis]]]
    const to = reference.target.max[axes[axis]] - reference.target.min[axes[axis]]
    numerator += from * to; denominator += from * from
  }
  const scale = numerator / denominator, translation = [0,0,0]
  for (const reference of references) for (let axis = 0; axis < 3; axis++) {
    const from = (reference.original.min[axes[permutation[axis]]] + reference.original.max[axes[permutation[axis]]]) / 2
    const to = (reference.target.min[axes[axis]] + reference.target.max[axes[axis]]) / 2
    translation[axis] += (to - scale * signs[axis] * from) / references.length
  }
  const residuals = []
  for (const reference of references) for (let axis = 0; axis < 3; axis++) for (const end of ['min','max']) {
    const fromEnd = signs[axis] > 0 ? end : end === 'min' ? 'max' : 'min'
    residuals.push(Math.abs(scale * signs[axis] * reference.original[fromEnd][axes[permutation[axis]]] + translation[axis] - reference.target[end][axes[axis]]))
  }
  const error = Math.max(...residuals)
  if (!best || error < best.error) best = { permutation, signs, scale, translation, error }
}
if (best.error > .008) throw new Error(`Registration residual too large: ${best.error}`)
const matrix = new THREE.Matrix4().set(
  ...[0,1,2].flatMap(axis => [...[0,1,2].map(column => best.permutation[axis] === column ? best.scale * best.signs[axis] : 0), best.translation[axis]]),
  0,0,0,1,
)
if (matrix.determinant() <= 0) throw new Error('Mirrored anatomy is not permitted')
console.log('Recovered source registration:', best)

const document = new Document(), buffer = document.createBuffer(), scene = document.createScene()
const material = document.createMaterial('cortical-rose').setBaseColorFactor([.67,.4,.46,1]).setRoughnessFactor(.65)
const corticalBounds = new THREE.Box3(), point = new THREE.Vector3()
let sourceTriangles = 0
for (const source of manifest.components) {
  const original = await sourceGeometry(source)
  original.deleteAttribute('normal'); original.applyMatrix4(matrix)
  const geometry = mergeVertices(original, 1e-5); geometry.computeVertexNormals()
  const positions = geometry.getAttribute('position').array
  for (let index = 0; index < positions.length; index += 3) corticalBounds.expandByPoint(point.fromArray(positions, index))
  sourceTriangles += geometry.index.count / 3
  const primitive = document.createPrimitive()
    .setAttribute('POSITION', document.createAccessor().setType('VEC3').setArray(new Float32Array(positions)).setBuffer(buffer))
    .setAttribute('NORMAL', document.createAccessor().setType('VEC3').setArray(new Float32Array(geometry.getAttribute('normal').array)).setBuffer(buffer))
    .setIndices(document.createAccessor().setType('SCALAR').setArray(new Uint32Array(geometry.index.array)).setBuffer(buffer))
    .setMaterial(material)
  scene.addChild(document.createNode(`brain__${source.id}`).setMesh(document.createMesh(source.name).addPrimitive(primitive)))
  original.dispose(); geometry.dispose()
}
// Verify the new cortex occupies the cranial region, not merely the body AABB.
if (corticalBounds.min.y < 2.55 || corticalBounds.max.y > 3.18 || corticalBounds.min.x < -.32 || corticalBounds.max.x > .32) throw new Error('Cortex is outside the expected cranial region')
await document.transform(weld(), simplify({ simplifier: MeshoptSimplifier, ratio: .35, error: .001, lockBorder: true }), join({ keepNamed: false }), prune(), draco({ quantizePosition: 16, quantizeNormal: 12 }))
document.getRoot().listNodes().filter(node => node.getMesh()).forEach(node => node.setName('brain__FMA61830'))
const output = await io.writeBinary(document)
await fs.writeFile(new URL('public/models/anatomy-cerebrum.glb', root), output)
const triangles = document.getRoot().listMeshes().reduce((sum, mesh) => sum + mesh.listPrimitives().reduce((sum, primitive) => sum + primitive.getIndices().getCount()/3,0),0)
manifest.conversion = {
  matrixColumnMajor: matrix.toArray(), maxReferenceBoundsResidual: best.error,
  sourceTriangles, outputTriangles: triangles, outputBytes: output.length,
  outputSha256: createHash('sha256').update(output).digest('hex'),
  cortexBounds: { min: corticalBounds.min.toArray(), max: corticalBounds.max.toArray() },
  changes: 'Axis conversion, uniform scale and translation recovered from matching stomach, kidney and pons bounds; vertex welding, smoothed normals, bounded mesh simplification and Draco compression. Original gyri geometry, no procedural brain.',
}
await fs.writeFile(manifestUrl, JSON.stringify(manifest,null,2)+'\n')
console.log(manifest.conversion)
