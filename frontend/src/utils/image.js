// Downscale a data-URL image to a small, compressed thumbnail for product lists.
// Non-data-URL sources (file paths / remote URLs) are already light — returned as-is.
export function shrink(src, max = 360, quality = 0.6) {
  return new Promise((resolve) => {
    if (!src || typeof src !== 'string' || !src.startsWith('data:')) return resolve(src || null)
    const img = new Image()
    img.onload = () => {
      let { width, height } = img
      if (width > max || height > max) {
        const s = max / Math.max(width, height)
        width = Math.round(width * s)
        height = Math.round(height * s)
      }
      const c = document.createElement('canvas')
      c.width = width
      c.height = height
      c.getContext('2d').drawImage(img, 0, 0, width, height)
      resolve(c.toDataURL('image/jpeg', quality))
    }
    img.onerror = () => resolve(src)
    img.src = src
  })
}
