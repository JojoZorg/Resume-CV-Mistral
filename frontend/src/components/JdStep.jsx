import React, { useState } from 'react'
import { analyzeJd } from '../api.js'

export default function JdStep({ cv, jd, setJd, options, setOptions, onBack, onNext }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function analyze() {
    setLoading(true)
    setError(null)
    try {
      const result = await analyzeJd({ mode, text, url, file, filename: file?.name })
      setJd(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function update(field, value) {
    setJd({ ...jd, [field]: value })
  }

  return (
    <div className="jd-step">
      <section className="panel">
        <h3>2. Job description</h3>
        <div className="tabs">
          {['text', 'file', 'url'].map(m => (
            <button key={m} className={`tab ${mode === m ? 'active' : ''}`} onClick={() => setMode(m)}>
              {m === 'text' ? 'Paste text' : m === 'file' ? 'Upload PDF/DOCX' : 'URL'}
            </button>
          ))}
        </div>
        {mode === 'text' && (
          <textarea rows={10} placeholder="Paste the full job description here…" value={text} onChange={e => setText(e.target.value)} />
        )}
        {mode === 'file' && (
          <input type="file" accept=".pdf,.docx" onChange={e => setFile(e.target.files?.[0] || null)} />
        )}
        {mode === 'url' && (
          <>
            <input type="url" placeholder="https://…" value={url} onChange={e => setUrl(e.target.value)} />
            <p className="hint">If the link shows a login wall, paste the text instead.</p>
          </>
        )}
        <button className="btn primary" onClick={analyze} disabled={loading}>
          {loading ? 'Analysing…' : 'Analyse JD'}
        </button>
        {error && <p className="error">{error}</p>}
      </section>

      {jd && (jd.required_skills?.length > 0 || jd.role_title) && (
        <section className="panel">
          <h3>Extracted requirements <small>(edit before tailoring)</small></h3>
          <div className="grid2">
            <label>Role title
              <input value={jd.role_title || ''} onChange={e => update('role_title', e.target.value)} />
            </label>
            <label>Seniority
              <input value={jd.seniority || ''} onChange={e => update('seniority', e.target.value)} />
            </label>
            <label>Years asked
              <input value={jd.years_of_experience || ''} onChange={e => update('years_of_experience', e.target.value)} />
            </label>
            <label>Domain
              <input value={jd.domain || ''} onChange={e => update('domain', e.target.value)} />
            </label>
          </div>
          <label>Required skills (comma-separated)
            <textarea rows={2} value={(jd.required_skills || []).join(', ')}
              onChange={e => update('required_skills', e.target.value.split(',').map(s => s.trim()).filter(Boolean))} />
          </label>
          <label>Nice to have (comma-separated)
            <textarea rows={2} value={(jd.preferred_skills || []).join(', ')}
              onChange={e => update('preferred_skills', e.target.value.split(',').map(s => s.trim()).filter(Boolean))} />
          </label>
          {jd.responsibilities?.length > 0 && (
            <div>
              <h4>Key responsibilities</h4>
              <ul className="plain">{jd.responsibilities.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
          {jd.soft_skills?.length > 0 && (
            <p><strong>Soft skills:</strong> {jd.soft_skills.join(', ')}</p>
          )}
          {jd.keywords?.length > 0 && (
            <p><strong>ATS keywords:</strong> {jd.keywords.join(', ')}</p>
          )}
        </section>
      )}

      {jd && (
        <section className="panel">
          <h3>Tailoring options</h3>
          <div className="grid2">
            <label>Tone
              <select value={options.tone} onChange={e => setOptions({ ...options, tone: e.target.value })}>
                <option value="original">Keep my voice</option>
                <option value="formal">Formal</option>
                <option value="conversational">Conversational</option>
              </select>
            </label>
            <label>Target language
              <select value={options.target_language} onChange={e => setOptions({ ...options, target_language: e.target.value })}>
                <option value="same">Same as CV</option>
                <option value="pt-BR">Português (BR)</option>
                <option value="en">English</option>
              </select>
            </label>
            <label>Max length
              <select value={options.max_pages} onChange={e => setOptions({ ...options, max_pages: parseInt(e.target.value, 10) })}>
                <option value={1}>1 page</option>
                <option value={2}>2 pages</option>
              </select>
            </label>
          </div>
          <label>Notes (e.g. "emphasize my Python work", "hide my 2015 role")
            <textarea rows={2} value={options.user_notes} onChange={e => setOptions({ ...options, user_notes: e.target.value })} />
          </label>
          <div className="step-actions">
            <button className="btn ghost" onClick={onBack}>← Back</button>
            <button className="btn primary" onClick={onNext}>Tailor →</button>
          </div>
        </section>
      )}

      {!jd && (
        <div className="step-actions">
          <button className="btn ghost" onClick={onBack}>← Back</button>
        </div>
      )}
    </div>
  )
}
