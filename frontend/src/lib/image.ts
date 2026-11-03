// Mirrors reader.py's current limits for early feedback; Python revalidates bytes.
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024
export const MAX_IMAGE_PIXELS = 8_000_000
export function validateImageMetadata(size: number, width: number, height: number) {
  if (size <= 0) throw new Error('This file is empty. Choose another image.')
  if (size > MAX_IMAGE_BYTES) throw new Error('Choose an image smaller than or equal to 10 MiB.')
  if (width <= 0 || height <= 0 || width * height > MAX_IMAGE_PIXELS) throw new Error('Choose an image with at most 8 million pixels.')
}
export function detectImageType(bytes: Uint8Array): 'image/png' | 'image/jpeg' | null {
  if ([137,80,78,71,13,10,26,10].every((v,i) => bytes[i] === v)) return 'image/png'
  if (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return 'image/jpeg'
  return null
}
export async function validateImage(file: File): Promise<{ width: number; height: number }> {
  if (!file.size || file.size > MAX_IMAGE_BYTES) validateImageMetadata(file.size, 1, 1)
  const header = new Uint8Array(await file.slice(0, 32).arrayBuffer())
  const detected = detectImageType(header)
  if (!detected || (file.type && file.type !== detected)) throw new Error('Use a genuine PNG or JPEG image. Renaming a file does not convert it.')
  // PNG IHDR dimensions are checked before allocating decoded pixels.
  if (detected === 'image/png' && header.length >= 24) {
    const view = new DataView(header.buffer)
    validateImageMetadata(file.size, view.getUint32(16), view.getUint32(20))
  }
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    validateImageMetadata(file.size, image.naturalWidth, image.naturalHeight)
    return { width: image.naturalWidth, height: image.naturalHeight }
  } catch (error) {
    if (error instanceof Error && error.message.includes('million pixels')) throw error
    throw new Error('This image could not be decoded or exceeds the image limits. Choose a clear, readable PNG or JPEG.')
  } finally { URL.revokeObjectURL(url) }
}
