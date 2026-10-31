// Decode all shipped assets with the exact shipped WASM decoder, without WebGL.
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const root = path.resolve(__dirname, '../public')
const decoderModule = new Module(path.join(root, 'draco/draco_wasm_wrapper.js'))
decoderModule._compile(fs.readFileSync(decoderModule.id, 'utf8'), decoderModule.id)

decoderModule.exports({ wasmBinary: fs.readFileSync(path.join(root, 'draco/draco_decoder.wasm')) }).then(draco => {
  const decoder = new draco.Decoder()
  function verify(file) {
    const bytes = fs.readFileSync(path.join(root, 'models', file))
    assert.equal(bytes.readUInt32LE(0), 0x46546c67)
    const jsonLength = bytes.readUInt32LE(12)
    const json = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString())
    const binary = bytes.subarray(28 + jsonLength)
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity]
    let triangles = 0
    for (const mesh of json.meshes) for (const primitive of mesh.primitives) {
      const extension = primitive.extensions.KHR_draco_mesh_compression
      const view = json.bufferViews[extension.bufferView]
      const source = binary.subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength)
      const buffer = new draco.DecoderBuffer(); buffer.Init(new Int8Array(source), source.length)
      const geometry = new draco.Mesh(), values = new draco.DracoFloat32Array()
      try {
        const status = decoder.DecodeBufferToMesh(buffer, geometry)
        assert.ok(status.ok(), status.error_msg()); assert.ok(geometry.num_points() > 0)
        triangles += geometry.num_faces()
        const position = decoder.GetAttributeByUniqueId(geometry, extension.attributes.POSITION)
        assert.ok(decoder.GetAttributeFloatForAllPoints(geometry, position, values))
        for (let i = 0; i < values.size(); i++) {
          const value = values.GetValue(i); assert.ok(Number.isFinite(value))
          min[i % 3] = Math.min(min[i % 3], value); max[i % 3] = Math.max(max[i % 3], value)
        }
      } finally { draco.destroy(values); draco.destroy(geometry); draco.destroy(buffer) }
    }
    assert.ok(!json.images?.length, 'No embedded textures')
    if (file === 'anatomy-cerebrum.glb') {
      assert.equal(json.meshes.length, 1, 'Cortical components are batched into one mesh')
      assert.equal(json.meshes[0].primitives.length, 1, 'Cortex uses one material/draw call')
    }
    // Both exports retain one world frame; do not independently align model roots.
    json.nodes.forEach(node => { assert.ok(!node.translation && !node.rotation && !node.scale && !node.matrix) })
    console.log(`${file}: ${bytes.length} bytes, ${triangles} triangles, decoded bounds ${JSON.stringify({ min, max })}`)
    console.log(`SHA-256: ${crypto.createHash('sha256').update(bytes).digest('hex')}`)
    return { names: json.nodes.map(node => node.name || ''), min, max, triangles, sha256: crypto.createHash('sha256').update(bytes).digest('hex') }
  }
  try {
    const organs = verify('anatomy-organs.glb'), skin = verify('anatomy-skin.glb'), cortex = verify('anatomy-cerebrum.glb')
    assert.deepEqual(skin.names.filter(Boolean), ['world', 'skin__FMA7163'])
    for (const organ of ['heart', 'lungs', 'liver', 'stomach', 'kidneys', 'intestines']) assert.ok(organs.names.some(name => name.startsWith(organ + '__FMA')), organ)
    assert.equal(organs.names.filter(name => name.startsWith('kidneys__')).length, 2)
    for (let axis = 0; axis < 3; axis++) {
      assert.ok(organs.min[axis] >= skin.min[axis] - .002)
      assert.ok(organs.max[axis] <= skin.max[axis] + .002)
      assert.ok(cortex.min[axis] >= skin.min[axis] - .002)
      assert.ok(cortex.max[axis] <= skin.max[axis] + .002)
    }
    assert.ok(cortex.names.includes('brain__FMA61830'))
    assert.ok(cortex.min[0] < 0 && cortex.max[0] > 0, 'Both hemispheres cross the midline')
    assert.ok(cortex.min[1] > 2.55 && cortex.max[1] <= 3.18, 'Cortex lies in cranial region')
    assert.ok(cortex.max[1] > organs.max[1], 'Cortex extends above existing brainstem parts')
    const provenance = JSON.parse(fs.readFileSync(path.join(root,'models/brain-sources.json'),'utf8'))
    assert.equal(cortex.sha256, provenance.conversion.outputSha256)
    assert.ok(provenance.conversion.maxReferenceBoundsResidual < .008)
    console.log('All organ bounds lie inside matching skin bounds in the unmodified source frame; this is not a surface-level medical validation.')
  } finally { draco.destroy(decoder) }
}).catch(error => { console.error(error); process.exitCode = 1 })
