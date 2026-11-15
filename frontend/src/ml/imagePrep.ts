/**
 * Προετοιμασία φωτογραφίας στον browser (DPIA): από το video της κάμερας σε JPEG με μεγαλύτερη πλευρά ≤ 448 px και
 * ≤ 1 MB, μέσω canvas (άρα χωρίς EXIF / θέση). Το αποτέλεσμα είναι Blob ΜΟΝΟ στη μνήμη: ποτέ σε localStorage,
 * IndexedDB, Cache ή ουρά. Το food gate (φίλτρο «είναι φαγητό;» στη συσκευή) είναι εκτός αυτής της φάσης.
 */
export const MAX_EDGE_PX = 448
export const MAX_BYTES = 1_048_576

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('encode'))), 'image/jpeg', quality))
}

/** Καρέ από <video> → JPEG Blob. Τετράγωνη περικοπή στο κέντρο (το πλαίσιο πιάτου του S06). */
export async function captureFrame(video: HTMLVideoElement): Promise<Blob> {
  const vw = video.videoWidth, vh = video.videoHeight
  if (!vw || !vh) throw new Error('no_frame')
  const side = Math.min(vw, vh)
  const sx = (vw - side) / 2, sy = (vh - side) / 2
  const out = Math.min(MAX_EDGE_PX, side)
  const canvas = document.createElement('canvas')
  canvas.width = out
  canvas.height = out
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas')
  ctx.drawImage(video, sx, sy, side, side, 0, 0, out, out)
  let quality = 0.85
  let blob = await toBlob(canvas, quality)
  while (blob.size > MAX_BYTES && quality > 0.4) {           // πρακτικά δεν συμβαίνει στα 448 px
    quality -= 0.15
    blob = await toBlob(canvas, quality)
  }
  ctx.clearRect(0, 0, out, out)
  canvas.width = 0                                           // ελευθερώνει το bitmap
  return blob
}

/** Μέση φωτεινότητα (0–255) ενός μικρού δείγματος του καρέ, για την ήπια υπόδειξη «Λίγο σκοτεινά» (S06γ). */
export function frameBrightness(video: HTMLVideoElement, sample: HTMLCanvasElement): number | null {
  if (!video.videoWidth) return null
  sample.width = 16
  sample.height = 16
  const ctx = sample.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null
  ctx.drawImage(video, 0, 0, 16, 16)
  const d = ctx.getImageData(0, 0, 16, 16).data
  let sum = 0
  for (let i = 0; i < d.length; i += 4) sum += (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000
  return sum / (d.length / 4)
}
