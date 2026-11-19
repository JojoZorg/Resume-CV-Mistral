import React, { useEffect, useMemo, useState } from 'react'
import CvStep from './components/CvStep.jsx'
import JdStep from './components/JdStep.jsx'
import InsightsView from './components/Insights.jsx'
import DiffView from './components/DiffView.jsx'
import { tailor } from './api.js'

const STORAGE_KEY = 'cvtool.session.v1'

export default function App() {
  const [view, setView] = useState('cv') // cv | jd | review | insights
  const [cv, setCv] = useState(null)
  const [jd, setJd] = useState(null)
  const [options, setOptions] = useState({ tone: 'original', target_language: 'same', max_pages: 1, user_notes: '' })
  const [result, setResult] = useState(null)
  const [working, setWorking] = useState(null)
  const [tailoring, setTailoring] = useState(false)
  const [tailorError, setTailorError] = useState(null)
  const [privacyAck, setPrivacyAck] = useState(false)

  // Privacy: persist only on this device, never on the server. User can wipe it.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const saved = JSON.parse(raw)
        setCv(saved.cv || null)
        setPrivacyAck(true)
      }
    } catch { /* first run */ }
  }, [])

  function persist(nextCv) {
    try {
      if (nextCv) localStorage.setItem(STORAGE_KEY, JSON.stringify({ cv: nextCv }))
      else localStorage.removeItem(STORAGE_KEY)
    } catch { /* storage full / disabled - fine */ }
  }

  function updateCv(next) {
    setCv(next)
    persist(next)
  }

  function deleteAllData() {
    persist(null)
    setCv(null)
    setJd(null)
    setResult(null)
    setWorking(null)
    setView('cv')
  }

  async function runTailor() {
    if (!cv) { setView('cv'); return }
    setTailoring(true)
    setTailorError(null)
    setWorking(null)
    setView('review')
    try {
      const result = await tailor(cv, jd || {}, options)
      setResult(result)
      setWorking(null)
    } catch (err) {
      setTailorError(err.message)
    } finally {
      setTailoring(false)
    }
  }

  const steps = [
    { key: 'cv', label: '1 · CV' },
    { key: 'jd', label: '2 · Job description' },
    { key: 'review', label: '3 · Review & export' },
    { key: 'insights', label: 'Career insights' },
  ]

  return (
    <div className="app">
      <header className="app-header">
        <h1>CV Tailoring Tool</h1>
        <p className="privacy-note">
          Your CV and JD are analysed only from your own data. Nothing is retained
          beyond the session unless you save it on this device.
        </p>
      </header>

      <nav className="steps">
        {steps.map(s => (
          <button
            key={s.key}
            className={`step-btn ${view === s.key ? 'active' : ''}`}
            onClick={() => setView(s.key)}
            disabled={(s.key !== 'cv' && s.key !== 'insights' && !cv)}
          >
            {s.label}
          </button>
        ))}
        <button className="btn small danger" onClick={deleteAllData} title="Delete all stored data on this device">
          Delete my data
        </button>
      </nav>

      {!privacyAck && (
        <div className="privacy-banner">
          <p>
            <strong>Privacy first:</strong> uploaded CVs and JDs are not retained by the
            app beyond your session. When no cloud LLM is configured, everything runs
            locally. If you configure a cloud LLM, use a no-training / enterprise
            endpoint. Your data stays on this device between visits.
          </p>
          <button className="btn small" onClick={() => setPrivacyAck(true)}>Got it</button>
        </div>
      )}

      {view === 'cv' && <CvStep cv={cv} setCv={updateCv} onNext={() => setView('jd')} />}
      {view === 'jd' && (
        <JdStep
          cv={cv}
          jd={jd}
          setJd={setJd}
          options={options}
          setOptions={setOptions}
          onBack={() => setView('cv')}
          onNext={runTailor}
        />
      )}
      {view === 'review' && (
        <>
          {tailorError && (
            <section className="panel">
              <p className="error">{tailorError}</p>
              <button className="btn" onClick={runTailor}>Retry</button>
            </section>
          )}
          {tailoring && <p className="loading">Tailoring your CV…</p>}
          {!tailoring && !tailorError && (result || working) && (
            <DiffView
              cv={cv}
              result={result}
              working={working}
              onChangeWorking={setWorking}
              onTailor={runTailor}
              tailoring={tailoring}
            />
          )}
        </>
      )}
      {view === 'insights' && <InsightsView cv={cv} />}
    </div>
  )
}
