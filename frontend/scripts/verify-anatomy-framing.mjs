// Numerical projection checks on the actual shipped geometry. This does not
// measure browser CSS boxes and must not be reported as a rendered visual test.
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import ts from 'typescript'
import * as T from 'three'
import { NodeIO } from '@gltf-transform/core'
import { KHRDracoMeshCompression } from '@gltf-transform/extensions'
import draco from 'draco3dgltf'
const root = fileURLToPath(new URL('../', import.meta.url))
const temporary = path.join(root,'.anatomy-work/14l-framing-helper.mjs')
await fs.mkdir(path.dirname(temporary),{recursive:true})
const source = await fs.readFile(path.join(root,'src/components/anatomyAppearance.ts'),'utf8')
await fs.writeFile(temporary,ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText)
const { measureUpperBody, fitCamera, restingPose } = await import(pathToFileURL(temporary).href)
await fs.unlink(temporary)
const io = new NodeIO().registerExtensions([KHRDracoMeshCompression]).registerDependencies({'draco3d.decoder':await draco.createDecoderModule()})
const content = new T.Group(), organs=[], skin=[]
for (const filename of ['anatomy-organs.glb','anatomy-skin.glb','anatomy-cerebrum.glb']) {
  const document = await io.read(path.join(root,'public/models',filename))
  for (const node of document.getRoot().listNodes()) {
    if (!node.getMesh()) continue
    for (const primitive of node.getMesh().listPrimitives()) {
      const geometry = new T.BufferGeometry().setAttribute('position',new T.BufferAttribute(primitive.getAttribute('POSITION').getArray(),3))
      const mesh = new T.Mesh(geometry);mesh.name=node.getName();content.add(mesh)
      ;(filename.includes('skin')?skin:organs).push(mesh)
    }
  }
}
const bounds=measureUpperBody(content,organs,skin)
assert.ok(bounds)
assert.ok(bounds.min.y < -.82,'The crop must include the real lateral hands')
assert.ok(bounds.min.y > -1,'The composition must not expand down to the feet')
const center=bounds.getCenter(new T.Vector3()),centered=bounds.clone().translate(center.clone().negate())
console.log('Measured head-to-hands source bounds:',bounds.min.toArray(),bounds.max.toArray())
const viewports=[{page:1440,width:482,height:640},{page:1024,width:676,height:680},{page:768,width:704,height:620},{page:390,width:358,height:560}]
const point=new T.Vector3(),rotation=new T.Euler()
for (const viewport of viewports) {
  let tested=0
  for (const pose of [restingPose,{pitch:-.16,yaw:-1.05},{pitch:.2,yaw:.95}]) {
    const camera=new T.PerspectiveCamera(34,1,.1,60)
    fitCamera(camera,viewport.width,viewport.height,centered,pose)
    rotation.set(pose.pitch,pose.yaw,0)
    for (const mesh of [...organs,...skin]) {
      const positions=mesh.geometry.getAttribute('position')
      for(let index=0;index<positions.count;index++){
        point.fromBufferAttribute(positions,index)
        if(skin.includes(mesh)&&point.y<bounds.min.y)continue
        point.sub(center).applyEuler(rotation).project(camera)
        assert.ok(Math.abs(point.x)<=.951 && Math.abs(point.y)<=.951 && Math.abs(point.z)<1,`${viewport.page}px: ${mesh.name} outside frame`)
        tested++
      }
    }
  }
  console.log(`${viewport.page}px layout / ${viewport.width}x${viewport.height} assumed canvas: ${tested} actual-vertex projections passed`)
}
content.traverse(object=>{if(object instanceof T.Mesh){object.geometry.dispose();object.material.dispose()}})
