import React, { useState } from 'react'
import { insights as fetchInsights } from '../api.js'

function RoleList({ title, roles, emptyText }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {roles.length === 0 && <p className="hint">{emptyText}</p>}
      <ul className="role-list">
        {roles.map((r, i) => (
          <li key={i} className="role-card">
            <div className="role-head">
              <strong>{r.title}</strong>
              {r.score > 0 && <span className="score">{Math.round(r.score * 100)}% match</span>}
            </div>
            <p>{r.justification}</p>
            {r.evidence?.length > 0 && (
              <ul className="evidence">
                {r.evidence.map((ev, j) => <li key={j} className="evidence-quote">{ev}</li>)}
              </ul>
            )}
            {r.gaps?.length > 0 && (
              <ul className="gap-inline">
                {r.gaps.map((g, j) => <li key={j}>Gap: {g}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function Insights({ cv }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchInsights(cv))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="insights">
      <section className="panel">
        <h3>Career insights</h3>
        <p className="hint">
          Standalone analysis of your CV — no job description needed. Everything below is
          derived strictly from your CV; no recommendation is made that your CV does not
          plausibly support.
        </p>
        {!data && <button className="btn primary" onClick={run} disabled={loading || !cv}>
          {loading ? 'Analysing…' : 'Analyse my CV'}
        </button>}
        {error && <p className="error">{error}</p>}
      </section>

      {data && (
        <>
          <RoleList title="Strong fits — roles your CV already supports" roles={data.strong_fits} emptyText="No strong fits found from this CV yet." />
          <RoleList title="Adjacent / stretch roles — one step away" roles={data.adjacent_roles} emptyText="No adjacent roles found." />
          <RoleList title="Latent paths — you may not have considered these" roles={data.latent_paths} emptyText="No latent paths found." />

          <section className="panel">
            <h3>Skill inventory</h3>
            <ul className="skill-groups">
              {data.skill_inventory.map((g, i) => (
                <li key={i}>
                  <strong>{g.group}</strong> <em className="breadth">({g.breadth})</em>: {g.skills.join(', ')}
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h3>Gaps for the next level</h3>
            {data.next_level_gaps.length === 0 && <p className="hint">Nothing significant missing for the next level found.</p>}
            <ul className="plain">
              {data.next_level_gaps.map((g, i) => <li key={i}>{g}</li>)}
            </ul>
          </section>

          <section className="panel">
            <h3>Suggested next steps</h3>
            <ul className="plain">
              {data.next_steps.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}
