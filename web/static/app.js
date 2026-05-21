let es = null;

// ── tabs ──────────────────────────────────────────────────────────────────────
function showTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'results') loadJobs();
}

// ── status ────────────────────────────────────────────────────────────────────
function setStatus(text, cls) {
  const el = document.getElementById('status');
  el.className = 'status-badge ' + (cls || '');
  el.querySelector('.dot').className = 'dot' + (cls === 'running' ? ' pulse' : '');
  document.getElementById('statusText').textContent = text;
}

function setRunning(on) {
  document.getElementById('startBtn').disabled = on;
  document.getElementById('stopBtn').disabled = !on;
  if (on) setStatus('Running…', 'running');
}

// ── terminal ──────────────────────────────────────────────────────────────────
function appendLog(line) {
  const term = document.getElementById('terminal');
  const d = document.createElement('div');
  d.className = classifyLine(line);
  d.textContent = line;
  term.appendChild(d);
  term.scrollTop = term.scrollHeight;
}

function classifyLine(s) {
  if (!s) return 'log';
  if (s.includes('Saved:'))                          return 'log saved';
  if (s.includes('Found ') || s.includes('jobs.'))  return 'log found';
  if (s.includes('Navigating') || s.includes('Search page') || s.includes('──')) return 'log nav';
  if (s.includes('error') || s.includes('Error') || s.includes('Timeout') || s.includes('timed out')) return 'log err';
  if (s.includes('trying anyway') || s.includes('not found') || s.includes('not visible')) return 'log warn';
  return 'log info';
}

// ── scraper control ───────────────────────────────────────────────────────────
function startScrape() {
  const kw = document.getElementById('keywords').value.trim();
  if (!kw) { setStatus('Enter keywords first', 'error'); return; }

  document.getElementById('terminal').innerHTML = '';
  setRunning(true);

  fetch('/api/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      keywords: kw,
      max_jobs: parseInt(document.getElementById('max_jobs').value) || 50,
      output:   document.getElementById('output').value || 'data/jobs.csv',
      debug:    document.getElementById('debug').checked,
    }),
  })
    .then(r => r.json())
    .then(d => {
      if (d.error) { setStatus(d.error, 'error'); setRunning(false); return; }
      startLogStream(0);
    })
    .catch(e => { setStatus('Failed: ' + e, 'error'); setRunning(false); });
}

function stopScrape() {
  fetch('/api/stop', { method: 'POST' }).then(() => setStatus('Stopping…', ''));
}

function startLogStream(since) {
  if (es) es.close();
  es = new EventSource('/api/logs?since=' + since);

  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.__done__) {
      es.close(); es = null;
      setRunning(false);
      setStatus('Done', 'done');
      loadJobs();
      return;
    }
    appendLog(d);
  };

  es.onerror = () => {
    es.close(); es = null;
    fetch('/api/status').then(r => r.json()).then(s => {
      if (!s.running) { setRunning(false); setStatus('Finished', 'done'); }
    });
  };
}

// ── results table ─────────────────────────────────────────────────────────────
function loadJobs() {
  fetch('/api/jobs').then(r => r.json()).then(renderTable);
}

function renderTable(jobs) {
  const badge = document.getElementById('badge');
  if (jobs.length) { badge.textContent = jobs.length; badge.style.display = ''; }
  else badge.style.display = 'none';

  const tbody = document.getElementById('jobBody');
  tbody.innerHTML = '';

  if (!jobs.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="10">No jobs scraped yet — run the scraper first.</td></tr>';
    return;
  }

  jobs.forEach(job => {
    let skills = job.skills || '';
    try { skills = JSON.parse(skills).join(', '); } catch {}

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="wide"><a href="${esc(job.job_link)}" target="_blank" title="${esc(job.title)}">${esc(job.title || '—')}</a></td>
      <td>${esc(job.budget)}</td>
      <td>${esc(job.job_type)}</td>
      <td>${esc(job.duration)}</td>
      <td title="${esc(skills)}">${esc(skills)}</td>
      <td>${esc(job.category)}</td>
      <td>${esc(job.proposals)}</td>
      <td>${esc(job.client_country)}</td>
      <td>${esc(job.client_total_spent)}</td>
      <td><button class="btn btn-purple" style="padding:4px 10px;font-size:11px" onclick="openFinder(${jobs.indexOf(job)})">Find Poster</button></td>
    `;
    tbody.appendChild(tr);
  });

  // store full list for finder navigation
  localStorage.setItem('upwork_jobs', JSON.stringify(jobs));
}

function openFinder(idx) {
  const jobs = JSON.parse(localStorage.getItem('upwork_jobs') || '[]');
  if (!jobs[idx]) return;
  localStorage.setItem('selected_job', JSON.stringify(jobs[idx]));
  window.open('/finder', '_blank');
}

function esc(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── init ──────────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
  fetch('/api/status').then(r => r.json()).then(s => {
    if (s.running) { setRunning(true); startLogStream(0); }
  });
});
