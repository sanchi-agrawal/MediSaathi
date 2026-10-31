import * as T from 'three'

export const restingPose = { pitch: .025, yaw: -.26 }
export const rotationLimits = { pitch: [-.16, .2], yaw: [-1.05, .95] } as const
const palette = ['#c18b9e', '#973d4c', '#b78b94', '#743f38', '#c79b9d', '#8c485b', '#b99191']

export function organMaterial(id: number) {
  const material = new T.MeshPhysicalMaterial({
    color: palette[id], roughness: id === 2 ? .67 : id === 0 ? .62 : .53, metalness: 0,
    clearcoat: .08, clearcoatRoughness: .65, ior: 1.38,
    envMapIntensity: .3,
  })
  material.userData.baseColor = material.color.clone()
  return material
}

export function shellMaterial() {
  return new T.MeshPhysicalMaterial({
    color: '#45c8ff', transparent: true, opacity: .14,
    depthWrite: false, depthTest: true,
    roughness: .2, metalness: 0, transmission: 0, clearcoat: .08,
    envMapIntensity: .3, side: T.DoubleSide,
    // Both faces of this real skin mesh contribute to a recognizable surface.
    // Keep Three.js's normal back-face/front-face transparent passes and depth
    // testing; do not override alpha in a shader or draw through opaque organs.
    forceSinglePass: false,
  })
}

export function updateShellSelection(shells: T.Mesh[], selected: number, hover: number) {
  const opacity = hover >= 0 ? .09 : selected === 0 ? .10 : selected >= 0 ? .11 : .14
  shells.forEach(shell => { (shell.material as T.MeshPhysicalMaterial).opacity = opacity })
}

export function updateSelection(meshes: T.Mesh[], selected: number, hover: number) {
  meshes.forEach(mesh => {
    const material = mesh.material as T.MeshPhysicalMaterial
    const active = mesh.userData.organ === selected
    material.color.copy(material.userData.baseColor).multiplyScalar(active ? 1 : .82)
    material.emissive.set(active ? '#52202b' : mesh.userData.organ === hover ? '#17353e' : '#000000')
    material.emissiveIntensity = active ? .3 : .18
  })
}

/** Measure decoded geometry in the common content frame, excluding the body pose. */
export function measureUpperBody(content: T.Group, organs: T.Mesh[], skin: T.Mesh[]) {
  content.updateWorldMatrix(true, true)
  const inverse = content.matrixWorld.clone().invert(), point = new T.Vector3()
  const transforms = new Map<T.Mesh, T.Matrix4>()
  function visit(mesh: T.Mesh, accept: (point: T.Vector3) => void) {
    const positions = mesh.geometry.getAttribute('position')
    if (!positions) return
    const matrix = transforms.get(mesh) ?? new T.Matrix4().multiplyMatrices(inverse, mesh.matrixWorld)
    transforms.set(mesh, matrix)
    for (let index = 0; index < positions.count; index++) accept(point.fromBufferAttribute(positions, index).applyMatrix4(matrix))
  }
  const organBounds = new T.Box3()
  organs.forEach(mesh => visit(mesh, point => organBounds.expandByPoint(point)))
  if (organBounds.isEmpty()) return null
  // Infer the pelvis boundary from the organs, then include the actual lateral
  // arms/hands of this source's standing pose. This affects camera framing only.
  const organSize = organBounds.getSize(new T.Vector3())
  let floor = organBounds.min.y - organSize.y * .08
  const midX = (organBounds.min.x + organBounds.max.x) / 2
  const lateralThreshold = organSize.x * .7
  skin.forEach(mesh => visit(mesh, point => {
    if (Math.abs(point.x - midX) >= lateralThreshold) floor = Math.min(floor, point.y - organSize.y * .02)
  }))
  const bounds = organBounds.clone()
  skin.forEach(mesh => visit(mesh, point => { if (point.y >= floor) bounds.expandByPoint(point) }))
  bounds.min.y = floor
  return bounds
}

export function boxCorners(box: T.Box3) {
  return [box.min.x, box.max.x].flatMap(x => [box.min.y, box.max.y].flatMap(y => [box.min.z, box.max.z].map(z => new T.Vector3(x, y, z))))
}

/** Fit eight bounds corners for the current pose, without changing model scale. */
export function fitCamera(camera: T.PerspectiveCamera, width: number, height: number, bounds: T.Box3, pose = restingPose) {
  camera.aspect = width / Math.max(height, 1)
  const tan = Math.tan(T.MathUtils.degToRad(camera.fov / 2)), occupancy = .95
  const corners = boxCorners(bounds), point = new T.Vector3(), rotation = new T.Euler()
  let distance = 0
  // As the damped body turns, adjust distance smoothly with that same pose.
  // This avoids shrinking the resting hero to fit a much wider drag angle.
  rotation.set(pose.pitch, pose.yaw, 0)
  for (const corner of corners) {
    point.copy(corner).applyEuler(rotation)
    distance = Math.max(distance, point.z + Math.abs(point.y) / (tan * occupancy), point.z + Math.abs(point.x) / (tan * camera.aspect * occupancy))
  }
  camera.position.set(0, 0, distance)
  camera.near = Math.max(.01, distance / 100)
  camera.far = distance + bounds.getSize(new T.Vector3()).length() * 4
  camera.updateProjectionMatrix(); camera.updateMatrixWorld(true)
}
