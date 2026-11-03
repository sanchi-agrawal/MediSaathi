import { expect, it } from 'vitest'
import * as T from 'three'
import { boxCorners, fitCamera, measureUpperBody, organMaterial, restingPose, shellMaterial, updateSelection, updateShellSelection } from './anatomyAppearance'

it('keeps selected organ color natural and dims other organs without transparency', () => {
  const heart = new T.Mesh(new T.BufferGeometry(), organMaterial(1)); heart.userData.organ = 1
  const liver = new T.Mesh(new T.BufferGeometry(), organMaterial(3)); liver.userData.organ = 3
  const original = liver.material.color.clone()
  updateSelection([heart, liver], 1, -1)
  expect(liver.material.color.r).toBeLessThan(original.r)
  expect(liver.material.transparent).toBe(false)
  updateSelection([heart, liver], 3, -1)
  expect(liver.material.color.equals(original)).toBe(true)
  expect(liver.material.metalness).toBe(0)
})

it('measures real upper-body vertices in the shared frame and excludes legs', () => {
  function mesh(positions:number[]){const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(positions,3));return new T.Mesh(geometry)}
  const skin=mesh([-1.3,2,.1,1.3,2,.1,0,3.18,.5,0,-3.5,.4])
  const organ=mesh([-.5,-.13,.1,.5,2.1,.8]),content=new T.Group(),body=new T.Group()
  content.add(skin,organ);body.add(content);body.rotation.y=.8
  const bounds=measureUpperBody(content,[organ],[skin])!
  expect(bounds.max.y).toBeCloseTo(3.18);expect(bounds.min.y).toBeGreaterThan(-.4)
  expect(bounds.min.x).toBeCloseTo(-1.3);expect(bounds.max.x).toBeCloseTo(1.3)
  expect(skin.position.toArray()).toEqual([0,0,0]);expect(organ.scale.toArray()).toEqual([1,1,1])
})

it('includes the source hands below the abdominal crop while excluding feet',()=>{
  const geometry=new T.BufferGeometry()
  geometry.setAttribute('position',new T.Float32BufferAttribute([-1.3,2,.1,1.3,2,.1,0,3.18,.5,-1.2,-.8,.4,1.2,-.8,.4,0,-3.5,.4],3))
  const skin=new T.Mesh(geometry),organGeometry=new T.BufferGeometry()
  organGeometry.setAttribute('position',new T.Float32BufferAttribute([-.5,-.13,.1,.5,2.1,.8],3))
  const organ=new T.Mesh(organGeometry),content=new T.Group();content.add(skin,organ)
  const bounds=measureUpperBody(content,[organ],[skin])!
  expect(bounds.min.y).toBeLessThan(-.8);expect(bounds.min.y).toBeGreaterThan(-1)
  expect(skin.position.toArray()).toEqual([0,0,0]);expect(skin.scale.toArray()).toEqual([1,1,1])
})

it('keeps measured head, shoulders and organs inside the camera during rotation at every viewport size', () => {
  const bounds=new T.Box3(new T.Vector3(-1.34,-1.75,-.6),new T.Vector3(1.34,1.75,.6))
  // Canvas sizes corresponding to the 1440/1024/768/390 CSS layouts.
  for (const [width,height] of [[482,640],[676,680],[704,620],[358,560]]) {
    for(const pose of [restingPose,{pitch:-.16,yaw:-1.05},{pitch:.2,yaw:.95},{pitch:.1,yaw:.4}]){
      const camera=new T.PerspectiveCamera(34,1,.1,60)
      fitCamera(camera,width,height,bounds,pose)
      const projected=boxCorners(bounds).map(point=>point.applyEuler(new T.Euler(pose.pitch,pose.yaw,0)).project(camera))
      projected.forEach(point=>{expect(Math.abs(point.x)).toBeLessThanOrEqual(.95001);expect(Math.abs(point.y)).toBeLessThanOrEqual(.95001);expect(Math.abs(point.z)).toBeLessThan(1)})
      // The subject uses the available space instead of remaining a tiny inset.
      expect(Math.max(...projected.flatMap(point=>[Math.abs(point.x),Math.abs(point.y)]))).toBeGreaterThan(.94)
    }
  }
})

it('adapts camera distance to asset dimensions rather than a fixed model offset',()=>{
  const camera=new T.PerspectiveCamera(34,1,.1,60),bounds=new T.Box3(new T.Vector3(-1,-2,-.5),new T.Vector3(1,2,.5))
  fitCamera(camera,700,760,bounds);const distance=camera.position.z
  fitCamera(camera,700,760,bounds.clone().applyMatrix4(new T.Matrix4().makeScale(2,2,2)))
  expect(camera.position.z).toBeCloseTo(distance*2)
})

it('keeps a real double-sided body surface visible instead of multiplying its alpha away', () => {
  const material = shellMaterial()
  const shader = { vertexShader: '#include <common>\n#include <project_vertex>', fragmentShader: '#include <common>\n#include <opaque_fragment>', uniforms: {} }
  const fragment = shader.fragmentShader
  material.onBeforeCompile(shader as T.WebGLProgramParametersWithUniforms, {} as T.WebGLRenderer)
  expect(shader.fragmentShader).toBe(fragment)
  expect(material.side).toBe(T.DoubleSide)
  expect(material.opacity).toBeGreaterThanOrEqual(.08)
  expect(material.opacity).toBeLessThanOrEqual(.18)
  expect(material.depthTest).toBe(true)
  expect(material.depthWrite).toBe(false)
  expect(material.transmission).toBe(0)
  expect(material.forceSinglePass).toBe(false)
})

it('reduces the shell opacity on selection without making the torso disappear',()=>{
  const shell=new T.Mesh(new T.BufferGeometry(),shellMaterial())
  updateShellSelection([shell],-1,-1);const resting=shell.material.opacity
  updateShellSelection([shell],1,-1);const selected=shell.material.opacity
  updateShellSelection([shell],1,2);const hovered=shell.material.opacity
  expect(resting).toBeGreaterThan(selected);expect(selected).toBeGreaterThan(hovered)
  expect(hovered).toBeGreaterThanOrEqual(.08)
  expect(resting).toBeLessThanOrEqual(.18)
  updateShellSelection([shell],0,-1);expect(shell.material.opacity).toBeLessThan(selected)
  expect(shell.scale.toArray()).toEqual([1,1,1])
})
