import React, { useState } from 'react'
import { parseCv } from '../api.js'

export default function CvStep({ cv, setCv, onNext }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function upload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const parsed = await parseCv(file)
      setCv(parsed)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function updateExperience(entryId, patch) {
    setCv({ ...cv, experience: cv.experience.map(e => e.id === entryId ? { ...e, ...patch } : e) })
  }

  function updateBullet(entryId, idx, text) {
    const entry = cv.experience.find(e => e.id === entryId)
    const bullets = entry.bullets.map((b, i) => i === idx ? text : b)
    updateExperience(entryId, { bullets })
  }

  function addBullet(entryId) {
    const entry = cv.experience.find(e => e.id === entryId)
    updateExperience(entryId, { bullets: [...entry.bullets, ''] })
  }

  function updateSkill(idx, text) {
    const skills = cv.skills.map((s, i) => i === idx ? text : s).filter(s => s.trim())
    setCv({ ...cv, skills })
  }

  function addSkill() {
    setCv({ ...cv, skills: [...cv.skills, ''] })
  }

  return (
    <div className="cv-step">
      <section className="panel">
        <h3>1. Upload your CV</h3>
        <p className="hint">PDF or DOCX. Scanned/image-only PDFs are rejected with a warning —
          upload a text-based PDF instead. Your file is processed in memory only, nothing is stored.</p>
        <input type="file" accept=".pdf,.docx" onChange={upload} />
        {loading && <p className="loading">Parsing…</p>}
        {error && <p className="error">{error}</p>}
      </section>

      {cv && (
        <section className="panel">
          <h3>Check &amp; correct the parsed structure</h3>
          {(cv.warnings || []).map((w, i) => <p key={i} className="warn">{w}</p>)}

          <div className="grid2">
            <label>Name
              <input value={cv.contact?.name || ''} onChange={e => setCv({ ...cv, contact: { ...cv.contact, name: e.target.value } })} />
            </label>
            <label>Email
              <input value={cv.contact?.email || ''} onChange={e => setCv({ ...cv, contact: { ...cv.contact, email: e.target.value } })} />
            </label>
            <label>Phone
              <input value={cv.contact?.phone || ''} onChange={e => setCv({ ...cv, contact: { ...cv.contact, phone: e.target.value } })} />
            </label>
            <label>Location
              <input value={cv.contact?.location || ''} onChange={e => setCv({ ...cv, contact: { ...cv.contact, location: e.target.value } })} />
            </label>
          </div>

          <label>Summary
            <textarea rows={3} value={cv.summary || ''} onChange={e => setCv({ ...cv, summary: e.target.value })} />
          </label>

          <h4>Experience</h4>
          {(cv.experience || []).length === 0 && <p className="warn">No experience entries detected — edit below or check the file.</p>}
          {(cv.experience || []).map(e => (
            <div key={e.id} className="entry-editor">
              <div className="grid2">
                <label>Title
                  <input value={e.title} onChange={ev => updateExperience(e.id, { title: ev.target.value })} />
                </label>
                <label>Company
                  <input value={e.company} onChange={ev => updateExperience(e.id, { company: ev.target.value })} />
                </label>
                <label>Start (MM/YYYY)
                  <input value={e.start} onChange={ev => updateExperience(e.id, { start: ev.target.value })} />
                </label>
                <label>End (MM/YYYY or Current)
                  <input value={e.end} onChange={ev => updateExperience(e.id, { end: ev.target.value })} />
                </label>
              </div>
              <ul className="bullet-list">
                {e.bullets.map((b, i) => (
                  <li key={i}>
                    <textarea rows={2} value={b} onChange={ev => updateBullet(e.id, i, ev.target.value)} />
                  </li>
                ))}
              </ul>
              <button className="btn small ghost" onClick={() => addBullet(e.id)}>+ Add bullet</button>
            </div>
          ))}

          <h4>Skills</h4>
          <ul className="skill-list">
            {(cv.skills || []).map((s, i) => (
              <li key={i}>
                <input value={s} onChange={e => updateSkill(i, e.target.value)} />
              </li>
            ))}
          </ul>
          <button className="btn small ghost" onClick={addSkill}>+ Add skill</button>

          <div className="step-actions">
            <button className="btn primary" onClick={onNext}>Next: Job description →</button>
          </div>
        </section>
      )}
    </div>
  )
}
