async function handle(resp) {
  let body = null
  try { body = await resp.json() } catch { /* ignore */ }
  if (!resp.ok) {
    const detail = body?.detail ?? body?.message ?? `HTTP ${resp.status}`
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return body
}

export async function parseCv(file) {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch('/api/parse-cv', { method: 'POST', body: form })
  return handle(resp)
}

export async function analyzeJd({ mode, text, url, file, filename }) {
  const payload = { mode, text: text || '', url: url || '', file_b64: '', filename: filename || '' }
  if (mode === 'file' && file) {
    const buf = await file.arrayBuffer()
    const bytes = new Uint8Array(buf)
    let bin = ''
    for (let i = 0; i < bytes.length; i += 0x8000) {
      bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
    }
    payload.file_b64 = btoa(bin)
    payload.filename = filename
  }
  const resp = await fetch('/api/analyze-jd', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handle(resp)
}

export async function tailor(cv, jd, options) {
  const resp = await fetch('/api/tailor', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cv, jd, options }),
  })
  return handle(resp)
}

export async function insights(cv) {
  const resp = await fetch('/api/insights', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cv),
  })
  return handle(resp)
}

export async function exportCv({ cv, tailored, format, reviewed, force, maxPages }) {
  const resp = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cv, tailored, format, reviewed, force, max_pages: maxPages }),
  })
  if (!resp.ok) {
    let body = null
    try { body = await resp.json() } catch { /* ignore */ }
    const err = new Error(body?.detail?.message || body?.detail || `HTTP ${resp.status}`)
    err.flags = body?.detail?.flags || null
    err.status = resp.status
    throw err
  }
  const blob = await resp.blob()
  const disp = resp.headers.get('Content-Disposition') || ''
  const match = disp.match(/filename="?([^";]+)"?/) || []
  return { blob, filename: match[1] || 'cv-download' }
}
