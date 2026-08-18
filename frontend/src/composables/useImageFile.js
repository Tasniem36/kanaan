// Downscale a picked file and encode it as a compact data URL, ready to POST.
//
// WebP is ~35% smaller than JPEG at the same visual quality, and the encoded string
// IS the upload payload — so this is most of what a slow phone connection spends
// its time on. Browsers that can't encode WebP silently hand back a PNG (much
// *larger*), so the result is checked and JPEG used instead.
//
// Shared by the manager's ImagePicker and the customer review form; the server
// re-encodes and caps again (backend/media.py), this only keeps the upload small.

const DEFAULT_MAX_DIM = 1400

function encode(canvas) {
  const webp = canvas.toDataURL('image/webp', 0.85)
  return webp.startsWith('data:image/webp') ? webp : canvas.toDataURL('image/jpeg', 0.82)
}

export function encodeImageFile(file, maxDim = DEFAULT_MAX_DIM) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > maxDim || height > maxDim) {
          const s = maxDim / Math.max(width, height)
          width = Math.round(width * s)
          height = Math.round(height * s)
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        canvas.getContext('2d').drawImage(img, 0, 0, width, height)
        resolve(encode(canvas))
      }
      img.onerror = reject
      img.src = reader.result
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
