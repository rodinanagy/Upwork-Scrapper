let job = null;

// ── init ──────────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
  const raw = localStorage.getItem('selected_job');
  if (!raw) {
    document.getElementById('jobCard').innerHTML =
      '<div style="color:var(--red)">No job selected. Go back and click "Find Poster" on a row.</div>';
    return;
  }
  job = JSON.parse(raw);

  const saved = localStorage.getItem('anthropic_api_key');
  if (saved) document.getElementById('apiKey').value = saved;

  renderJobCard(job);
});

// ── job card ──────────────────────────────────────────────────────────────────
function renderJobCard(j) {
  document.getElementById('navTitle').textContent = j.title || 'LinkedIn Finder';
  document.getElementById('jobLink').href = j.job_link || '#';

  let skills = j.skills || '';
  try { skills = JSON.parse(skills); } catch { skills = skills ? [skills] : []; }
  if (!Array.isArray(skills)) skills = [];

  document.getElementById('jobCard').innerHTML = `
    <h2>${esc(j.title || '(no title)')}</h2>
    <div class="meta-grid">
      ${meta('Budget',       j.budget)}
      ${meta('Type',         j.job_type)}
      ${meta('Duration',     j.duration)}
      ${meta('Exp. Level',   j.experience_level)}
      ${meta('Proposals',    j.proposals)}
      ${meta('Country',      j.client_country)}
      ${meta('Rating',       j.client_rating)}
      ${meta('Total Spent',  j.client_total_spent)}
      ${meta('Hires',        j.client_hires)}
      ${meta('Member Since', j.client_member_since)}
    </div>
    ${skills.length ? `
      <div class="field">
        <div class="meta-label">Skills</div>
        <div class="skills-wrap">${skills.map(s => `<span class="skill-tag">${esc(s)}</span>`).join('')}</div>
      </div>` : ''}
    ${j.description ? `
      <div class="field">
        <div class="meta-label">Description</div>
        <div class="desc-box">${esc(j.description)}</div>
      </div>` : ''}
  `;
}

function meta(label, value) {
  if (!value) return '';
  return `<div class="meta-item">
    <div class="meta-label">${esc(label)}</div>
    <div class="meta-value">${esc(value)}</div>
  </div>`;
}

// ── find poster ───────────────────────────────────────────────────────────────
function findPoster() {
  if (!job) return;

  const apiKey = document.getElementById('apiKey').value.trim();
  if (apiKey) localStorage.setItem('anthropic_api_key', apiKey);

  document.getElementById('searchBtn').disabled = true;
  document.getElementById('searchBtn').textContent = '⏳ Searching…';

  // Build result area: search activity log + text output
  const area = document.getElementById('resultArea');
  area.innerHTML = `
    <div id="activityBox" style="
      background:var(--bg3); border:1px solid var(--border); border-radius:6px;
      padding:14px 16px; margin-bottom:20px; font-size:12px;
      font-family:'SF Mono',monospace; line-height:1.8;">
      <div style="color:var(--muted); margin-bottom:8px; font-size:11px; text-transform:uppercase; letter-spacing:.5px;">
        🤖 Agent activity
      </div>
      <div id="searchList"></div>
    </div>
    <div id="resultContent" class="result-content"></div>
  `;

  let buffer = '';
  let lastSearchEl = null;

  function addSearch(query) {
    const div = document.createElement('div');
    div.style.cssText = 'display:flex; align-items:center; gap:8px; color:var(--muted);';
    div.innerHTML = `<span style="color:var(--accent)">🔍</span> <span style="color:var(--text)">${esc(query)}</span>`;
    document.getElementById('searchList').appendChild(div);
    lastSearchEl = div;
    area.scrollTop = 0;
  }

  function markResult(count) {
    if (!lastSearchEl) return;
    const tag = document.createElement('span');
    tag.style.cssText = `margin-left:auto; color:${count > 0 ? 'var(--green)' : 'var(--muted)'};`;
    tag.textContent = count > 0 ? `→ ${count} results` : '→ no results';
    lastSearchEl.appendChild(tag);
  }

  fetch('/api/find-poster', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job, api_key: apiKey }),
  }).then(async resp => {
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: 'Request failed' }));
      area.innerHTML = `<div style="color:var(--red); padding:20px">${esc(err.error || 'Request failed')}</div>`;
      resetBtn(); return;
    }

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let partial   = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      partial += decoder.decode(value, { stream: true });
      const lines = partial.split('\n');
      partial = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let d;
        try { d = JSON.parse(line.slice(6)); } catch { continue; }

        if (d.type === 'search') {
          addSearch(d.query);
        } else if (d.type === 'result') {
          markResult(d.count);
        } else if (d.type === 'text') {
          buffer += d.text;
          const el = document.getElementById('resultContent');
          el.textContent = buffer;          // live raw text while streaming
          area.scrollTop = area.scrollHeight;
        } else if (d.type === 'done') {
          // Render markdown and make LinkedIn links pretty
          const el = document.getElementById('resultContent');
          el.innerHTML = renderMarkdown(buffer);
          styleLinkedInLinks(el);
          // Dim the activity box
          document.getElementById('activityBox').style.opacity = '0.5';
          resetBtn(); return;
        } else if (d.type === 'error') {
          document.getElementById('resultContent').innerHTML =
            `<div style="color:var(--red)">${esc(d.message)}</div>`;
          resetBtn(); return;
        }
      }
    }
    resetBtn();
  }).catch(e => {
    area.innerHTML = `<div style="color:var(--red); padding:20px">Error: ${esc(String(e))}</div>`;
    resetBtn();
  });
}

function resetBtn() {
  const btn = document.getElementById('searchBtn');
  btn.disabled = false;
  btn.textContent = '🔎 Find on LinkedIn';
}

// ── markdown renderer ─────────────────────────────────────────────────────────
function renderMarkdown(md) {
  let h = esc(md);

  // headings
  h = h.replace(/^### (.+)$/gm, '<h3 style="font-size:13px;font-weight:700;margin:14px 0 6px">$1</h3>');
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');

  // bold
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // inline code
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');

  // raw URLs → links
  h = h.replace(/(https?:\/\/[^\s<&"]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');

  // bullet lists
  h = h.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');

  // paragraphs
  h = '<p>' + h.replace(/\n\n/g, '</p><p>') + '</p>';
  h = h.replace(/<p>\s*<\/p>/g, '');
  h = h.replace(/<p>(<[hul])/g, '$1').replace(/(<\/[hul][^>]*>)<\/p>/g, '$1');

  return h;
}

// Make linkedin.com links look like buttons
function styleLinkedInLinks(container) {
  container.querySelectorAll('a').forEach(a => {
    if (!a.href.includes('linkedin.com')) return;
    a.className = 'linkedin-link';
    // If the URL is a profile URL (/in/...), label it as a profile
    const isProfile = a.href.includes('/in/');
    const path = new URL(a.href).pathname.replace(/\/$/, '');
    const name = path.split('/').pop().replace(/-/g, ' ');
    a.textContent = isProfile
      ? `🔗 ${name || 'View Profile'}`
      : `🔗 ${decodeURIComponent(new URL(a.href).searchParams.get('keywords') || 'LinkedIn Search')}`;
  });
}

function esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
