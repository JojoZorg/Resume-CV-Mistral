import React, { useState, useMemo, useRef, useEffect } from 'react'
import { diffWords } from '../diff.js'
import { exportCv } from '../api.js'

function WordDiff({ original, current }) {
  const tokens = useMemo(() => {
    if ((original || '') === (current || '')) return [{ type: 'same', text: current || '' }]
    return diffWords(original, current)
  }, [original, current])
  return (
    <span className="worddiff">
      {tokens.map((t, i) =>
        t.type === 'same' ? <span key={i}>{t.text}</span>
          : t.type === 'add' ? <span key={i} className="diff-add">{t.text}</span>
            : <span key={i} className="diff-del">{t.text}</span>,
      )}
    </span>
  )
}

function OriginalBullet({ id, text, highlighted, reworded }) {
  return (
    <li
      id={`orig-${id}`}
      className={[
        'orig-bullet',
        highlighted ? 'highlighted' : '',
        reworded ? 'reworded' : '',
      ].join(' ')}
    >
      {text || <em>(empty)</em>}
    </li>
  )
}

function TailoredBullet({ entryId, index, bullet, originalText, edited, onChange, onRevert, onTrace }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(bullet.text)
  const changed = (originalText || '') !== (bullet.text || '') || edited

  useEffect(() => { setDraft(bullet.text) }, [bullet.text])

  return (
    <li className={`tail-bullet ${changed ? 'changed' : ''}`}>
      {editing ? (
        <>
          <textarea
            value={draft}
            rows={3}
            onChange={e => setDraft(e.target.value)}
            className="bullet-editor"
          />
          <div className="bullet-actions">
            <button className="btn small" onClick={() => { onChange(draft); setEditing(false) }}>Save</button>
            <button className="btn small ghost" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          <WordDiff original={originalText} current={bullet.text} />
          <div className="bullet-actions">
            <a
              className="trace-link"
              href={`#orig-${bullet.source_ids[0] || ''}`}
              onClick={e => { e.preventDefault(); onTrace(bullet.source_ids[0]) }}
            >
              Trace
            </a>
            <button className="btn small ghost" onClick={() => setEditing(true)}>Edit</button>
            {changed && (
              <button className="btn small ghost" onClick={onRevert}>Revert</button>
            )}
          </div>
        </>
      )}
    </li>
  )
}

export default function DiffView({ cv, working, result, onChangeWorking, onTailor, tailoring }) {
  const [reviewed, setReviewed] = useState(false)
  const [highlightSid, setHighlightSid] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [exportMessage, setExportMessage] = useState(null)
  const [force, setForce] = useState(false)
  const exporting = useRef(false)

  const fabrication = result?.fabrication
  const gaps = result?.gaps || []
  const diffCounts = result?.diff?.counts || []

  const fallbackWorking = useMemo(() => ({
    tailored: {
      contact: cv.contact,
      summary: cv.summary,
      summary_source_ids: [],
      role_title: '',
      experience: cv.experience.map(e => ({
        ...e,
        bullets: e.bullets.map((t, i) => ({ text: t, source_ids: [`${e.id}#${i}`], change: 'kept' })),
      })),
      education: cv.education,
      skills: cv.skills,
      certifications: cv.certifications,
      languages: cv.languages,
      projects: (cv.projects || []).map(p => ({
        ...p,
        bullets: p.bullets.map((t, i) => ({ text: t, source_ids: [`${p.id}#${i}`], change: 'kept' })),
      })),
      excluded_bullet_ids: [],
      notes: '',
    },
    fabrication: { flags: [], passed: true },
    gaps: [],
    diff: { counts: [], total: 0 },
    export_hint: 'Use the ATS version for online portals and job boards; use the designed version for direct emails, referrals, and recruiters.',
  }), [cv])

  const active = working || result || fallbackWorking
  const tailored = active.tailored
  const originalBySection = useMemo(() => {
    const map = {}
    for (const e of cv.experience) map[e.id] = e
    return map
  }, [cv])

  const originalProjectMap = useMemo(() => {
    const map = {}
    for (const p of (cv.projects || [])) map[p.id] = p
    return map
  }, [cv])

  function sourceTextOf(sid) {
    if (!sid) return ''
    const [eid, idxStr] = sid.split('#')
    const entry = originalBySection[eid]
    if (entry) return entry.bullets[parseInt(idxStr, 10)] || ''
    const proj = originalProjectMap[eid]
    if (proj) return proj.bullets[parseInt(idxStr, 10)] || ''
    return ''
  }

  function setWorking(next) {
    onChangeWorking({ ...active, tailored: next })
  }

  function updateBullet(listPath, entryId, bIndex, updater) {
    const next = JSON.parse(JSON.stringify(tailored))
    const list = listPath === 'projects' ? next.projects : next.experience
    const entry = list.find(e => e.id === entryId)
    if (!entry) return
    updater(entry.bullets[bIndex])
    setWorking(next)
  }

  function revertBullet(entryId, bIndex, listPath) {
    updateBullet(listPath, entryId, bIndex, b => {
      const src = b.source_ids[0]
      b.text = sourceTextOf(src)
      b.change = 'kept'
    })
  }

  function scrollToOrigin(sid) {
    setHighlightSid(sid)
    setTimeout(() => setHighlightSid(null), 2200)
    const el = sid && document.getElementById(`orig-${sid}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  async function doExport(format) {
    setExportError(null)
    setExportMessage(null)
    exporting.current = true
    try {
      const { blob, filename } = await exportCv({
        cv,
        tailored,
        format,
        reviewed,
        force,
        maxPages: 2,
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      setExportMessage(`Downloaded ${filename}`)
    } catch (err) {
      setExportError(err)
    } finally {
      exporting.current = false
    }
  }

  const fabricationFlags = fabrication?.flags || []

  return (
    <div className="diff-view">
      {gaps.length > 0 && (
        <section className="panel gaps">
          <h3>Gaps — JD requirements not found in your CV (never silently hidden)</h3>
          <ul>
            {gaps.map((g, i) => (
              <li key={i} className={g.status === 'missing' ? 'gap-missing' : 'gap-pref'}>
                <strong>{g.requirement}</strong> — {g.message}
                <ul className="gap-suggestions">
                  {(g.suggestions || []).map((s, j) => <li key={j}>{s}</li>)}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      {fabricationFlags.length > 0 && (
        <section className="panel fabrication-warning">
          <h3>Fabrication check: {fabricationFlags.length} flag(s) — export blocked</h3>
          <ul>
            {fabricationFlags.map((f, i) => (
              <li key={i}>
                <strong>{f.kind}</strong>&nbsp;
                <code>{f.value}</code> — {f.detail} <span className="loc">({f.location})</span>
              </li>
            ))}
          </ul>
          <p>Fix the flagged content by editing or reverting the bullets below.</p>
          <label className="force-row">
            <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} />
            Override and export anyway (explicit acknowledgte)
          </label>
        </section>
      )}

      {fabricationFlags.length === 0 && (
        <p className="fabrication-ok">Fabrication check passed: every bullet traces to your original CV ({fabrication?.checked_entities ?? 0} entities verified).</p>
      )}

      {tailored.notes && <p className="notes-banner">{tailored.notes}</p>}

      <section className="panel diff-counts">
        <h3>Change summary {result?.diff ? `(${result.diff.total} changes)` : ''}</h3>
        <ul className="counts">
          {diffCounts.length === 0 && <li>No changes — the CV already matches the JD ordering.</li>}
          {diffCounts.map(c => (
            <li key={c.section}>
              {c.section}: {c.reworded} reworded, {c.removed} removed
            </li>
          ))}
        </ul>
        <button className="btn ghost" onClick={onTailor} disabled={tailoring}>
          {tailoring ? 'Tailoring…' : 'Regenerate'}
        </button>
      </section>

      <div className="side-by-side">
        <div className="pane">
          <h3>Original</h3>
          {cv.summary && <p className="orig-summary" id="orig-summary">{cv.summary}</p>}
          {cv.experience.map(e => (
            <div key={e.id} className="orig-entry">
              <p className="orig-role"><strong>{e.title}</strong>{e.company && `, ${e.company}`} <span className="dates">{e.start} – {e.end}</span></p>
              <ul>
                {e.bullets.map((b, i) => (
                  <OriginalBullet
                    key={i}
                    id={`${e.id}#${i}`}
                    text={b}
                    highlighted={highlightSid === `${e.id}#${i}`}
                    reworded={false}
                  />
                ))}
              </ul>
            </div>
          ))}
          {(cv.projects || []).map(p => (
            <div key={p.id} className="orig-entry">
              <p className="orig-role"><strong>Project: {p.name}</strong></p>
              <ul>
                {p.bullets.map((b, i) => (
                  <OriginalBullet key={i} id={`${p.id}#${i}`} text={b} highlighted={highlightSid === `${p.id}#${i}`} />
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="pane">
          <h3>Tailored {tailored.role_title && <span className="role-chip">→ {tailored.role_title}</span>}</h3>
          <p className="orig-summary">{tailored.summary}</p>
          {tailored.experience.map(e => (
            <div key={e.id} className="orig-entry">
              <p className="orig-role"><strong>{e.title}</strong>{e.company && `, ${e.company}`} <span className="dates">{e.start} – {e.end}</span></p>
              <ul>
                {(e.bullets || []).map((b, i) => (
                  <TailoredBullet
                    key={i}
                    entryId={e.id}
                    index={i}
                    bullet={b}
                    originalText={sourceTextOf(b.source_ids[0])}
                    edited={false}
                    onChange={text => updateBullet('experience', e.id, i, x => { x.text = text })}
                    onRevert={() => revertBullet(e.id, i, 'experience')}
                    onTrace={scrollToOrigin}
                  />
                ))}
              </ul>
            </div>
          ))}
          {(tailored.projects || []).map(p => (
            <div key={p.id} className="orig-entry">
              <p className="orig-role"><strong>Project: {p.name}</strong></p>
              <ul>
                {p.bullets.map((b, i) => (
                  <TailoredBullet
                    key={i}
                    entryId={p.id}
                    index={i}
                    bullet={b}
                    originalText={sourceTextOf(b.source_ids[0])}
                    onChange={text => updateBullet('projects', p.id, i, x => { x.text = text })}
                    onRevert={() => revertBullet(p.id, i, 'projects')}
                    onTrace={scrollToOrigin}
                  />
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <section className="panel export-panel">
        <h3>Export</h3>
        <p className="hint">{active.export_hint}</p>
        <label className="review-row">
          <input
            type="checkbox"
            checked={reviewed}
            onChange={e => setReviewed(e.target.checked)}
          />
          I have reviewed all changes above
        </label>
        <div className="export-buttons">
          <button className="btn" disabled={!reviewed || exporting.current} onClick={() => doExport('ats_pdf')}>Download ATS PDF</button>
          <button className="btn" disabled={!reviewed || exporting.current} onClick={() => doExport('ats_docx')}>Download ATS DOCX</button>
          <button className="btn" disabled={!reviewed || exporting.current} onClick={() => doExport('designed_pdf')}>Download Designed PDF</button>
        </div>
        {exportMessage && <p className="export-ok">{exportMessage}</p>}
        {exportError && (
          <p className="export-error">
            {exportError.message}
            {exportError.flags && <ul>{exportError.flags.map((f, i) => <li key={i}>{f.kind}: {f.value} — {f.detail}</li>)}</ul>}
          </p>
        )}
      </section>
    </div>
  )
}
