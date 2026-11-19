// Small word-level diff (LCS) with no external dependency.
// Returns a flat list of tokens: { type: 'same' | 'add' | 'del', text }

function tokenize(text) {
  return (text || '').split(/(\s+)/).filter(t => t !== '')
}

export function diffWords(oldText, newText) {
  const a = tokenize(oldText)
  const b = tokenize(newText)
  const n = a.length
  const m = b.length
  // LCS table (fine for CV-sized strings)
  const lowerA = a.map(t => t.toLowerCase())
  const lowerB = b.map(t => t.toLowerCase())
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = lowerA[i] === lowerB[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const tokens = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (lowerA[i] === lowerB[j]) {
      tokens.push({ type: 'same', text: b[j] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      tokens.push({ type: 'del', text: a[i] })
      i++
    } else {
      tokens.push({ type: 'add', text: b[j] })
      j++
    }
  }
  while (i < n) tokens.push({ type: 'del', text: a[i++] })
  while (j < m) tokens.push({ type: 'add', text: b[j++] })
  return tokens
}

export function isReworded(oldText, newText) {
  if ((oldText || '') === (newText || '')) return false
  return true
}
