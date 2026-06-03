const defaults = {
  theme: 'dark',
  accent: '#ff4d6d',
  autoRefresh: true,
  compactMode: false,
  showReviewed: false,
  sort: 'confidence',
};

const state = {
  tracks: [],
  selected: null,
  settings: { ...defaults, ...JSON.parse(localStorage.getItem('beatAnalyzerSettings') || '{}') },
  refreshTimer: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(await res.text());
  return res.headers.get('content-type')?.includes('application/json') ? res.json() : res.text();
}

function saveSettings() {
  localStorage.setItem('beatAnalyzerSettings', JSON.stringify(state.settings));
  applySettings();
}

function applySettings() {
  const theme = state.settings.theme === 'system'
    ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : state.settings.theme;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.setProperty('--accent', state.settings.accent);
  document.body.classList.toggle('compact', state.settings.compactMode);
  $('showReviewed').checked = state.settings.showReviewed;
  $('sortSelect').value = state.settings.sort;
  $('themeSelect').value = state.settings.theme;
  $('accentInput').value = state.settings.accent;
  $('autoRefresh').checked = state.settings.autoRefresh;
  $('compactMode').checked = state.settings.compactMode;
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  state.refreshTimer = state.settings.autoRefresh ? setInterval(loadTracks, 10000) : null;
}

function pct(value) {
  return value == null ? '—' : `${Math.round(value * 100)}%`;
}

function secs(value) {
  return value == null ? '—' : `${Number(value).toFixed(3)}s`;
}

function activeAnalysis() {
  return state.selected?.corrected_analysis || state.selected?.raw_analysis;
}

async function loadServerSettings() {
  try {
    const settings = await api('/api/settings');
    $('serverSettings').textContent = JSON.stringify(settings, null, 2);
  } catch (error) {
    $('serverSettings').textContent = `Unable to load server settings: ${error.message}`;
  }
}

async function loadTracks() {
  state.tracks = await api('/api/tracks');
  renderTrackList();
}

function filteredTracks() {
  const term = $('searchInput').value.trim().toLowerCase();
  let tracks = state.tracks.filter((track) => state.settings.showReviewed || track.review_status !== 'reviewed');
  if (term) tracks = tracks.filter((track) => track.filename.toLowerCase().includes(term));
  const confidence = (track) => track.confidence?.salsa_one ?? 0;
  tracks.sort((a, b) => {
    if (state.settings.sort === 'name') return a.filename.localeCompare(b.filename);
    if (state.settings.sort === 'bpm') return (a.bpm || 0) - (b.bpm || 0);
    if (state.settings.sort === 'newest') return 0;
    return confidence(a) - confidence(b);
  });
  return tracks;
}

function renderTrackList() {
  const list = $('trackList');
  const tracks = filteredTracks();
  $('trackCount').textContent = `${tracks.length} track${tracks.length === 1 ? '' : 's'}`;
  list.innerHTML = '';
  if (!tracks.length) {
    list.innerHTML = '<p class="empty">No tracks match this view. Try Scan /import, upload files, or enable reviewed tracks.</p>';
    return;
  }
  tracks.forEach((track) => {
    const card = document.createElement('button');
    card.className = `track-card ${state.selected?.id === track.id ? 'active' : ''}`;
    card.innerHTML = `
      <strong>${track.filename}</strong>
      <p>${track.status} · ${track.imported ? 'imported' : 'uploaded'} · review: ${track.review_status}</p>
      <div class="meta">
        <span class="pill">BPM ${track.bpm ?? '—'}</span>
        <span class="pill">1 ${secs(track.candidate_salsa_1)}</span>
        <span class="pill">5 ${secs(track.candidate_salsa_5)}</span>
        <span class="pill ${track.review_status === 'reviewed' ? 'ok' : 'warn'}">one ${pct(track.confidence?.salsa_one)}</span>
      </div>`;
    card.addEventListener('click', () => selectTrack(track.id));
    list.appendChild(card);
  });
}

async function selectTrack(id) {
  state.selected = await api(`/api/tracks/${id}`);
  renderTrackList();
  renderDetail();
  await drawWaveform();
}

function renderDetail() {
  $('emptyState').hidden = true;
  $('trackDetail').hidden = false;
  $('detailTitle').textContent = state.selected.filename;
  $('detailSubtitle').textContent = state.selected.imported ? `Imported from ${state.selected.source_path}` : 'Uploaded through browser';
  $('audio').src = `/api/tracks/${state.selected.id}/audio`;
  $('jsonExport').href = `/api/tracks/${state.selected.id}/exports/analysis.json`;
  $('beatExport').href = `/api/tracks/${state.selected.id}/exports/beats.csv`;
  const analysis = activeAnalysis();
  const conf = analysis?.confidence || {};
  $('metrics').innerHTML = [
    ['BPM', analysis?.bpm ?? '—'],
    ['Half display', analysis?.bpm_display_half ?? '—'],
    ['Candidate 1', secs(analysis?.candidate_salsa_1)],
    ['Candidate 5', secs(analysis?.candidate_salsa_5)],
    ['BPM confidence', pct(conf.bpm)],
    ['Grid confidence', pct(conf.grid)],
    ['Downbeat confidence', pct(conf.downbeat)],
    ['Salsa 1 confidence', pct(conf.salsa_one)],
  ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');
  $('warnings').innerHTML = (analysis?.warnings || []).map((w) => `<p>⚠️ ${w}</p>`).join('');
}

async function drawWaveform() {
  const canvas = $('waveform');
  const ctx = canvas.getContext('2d');
  const analysis = activeAnalysis();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--wave-bg');
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!state.selected) return;
  try {
    const audioData = await fetch(`/api/tracks/${state.selected.id}/audio`).then((r) => r.arrayBuffer());
    const audioCtx = new AudioContext();
    const audioBuffer = await audioCtx.decodeAudioData(audioData.slice(0));
    const data = audioBuffer.getChannelData(0);
    const step = Math.ceil(data.length / canvas.width);
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--wave-line');
    ctx.beginPath();
    for (let x = 0; x < canvas.width; x++) {
      let min = 1;
      let max = -1;
      for (let i = 0; i < step; i++) {
        const datum = data[(x * step) + i] || 0;
        min = Math.min(min, datum);
        max = Math.max(max, datum);
      }
      ctx.moveTo(x, (1 + min) * canvas.height / 2);
      ctx.lineTo(x, (1 + max) * canvas.height / 2);
    }
    ctx.stroke();
    audioCtx.close();
  } catch (error) {
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--muted');
    ctx.fillText('Waveform preview unavailable in this browser for this codec.', 24, 42);
  }
  drawMarkers(canvas, ctx, analysis);
}

function drawMarkers(canvas, ctx, analysis) {
  if (!analysis?.beats?.length || !analysis.duration) return;
  const styles = getComputedStyle(document.documentElement);
  const accentTwo = styles.getPropertyValue('--accent-2');
  const gridLine = styles.getPropertyValue('--grid-line');
  for (const beat of analysis.beats) {
    const x = (beat.time / analysis.duration) * canvas.width;
    ctx.strokeStyle = beat.is_salsa_1 ? state.settings.accent : beat.is_salsa_5 ? accentTwo : gridLine;
    ctx.lineWidth = beat.is_salsa_1 || beat.is_salsa_5 ? 2 : 1;
    ctx.beginPath();
    ctx.moveTo(x, beat.is_downbeat ? 0 : 42);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
    if (beat.is_salsa_1 || beat.is_salsa_5) {
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fillText(String(beat.count8), x + 3, 18);
    }
  }
}

async function uploadFiles() {
  const files = Array.from($('fileInput').files || []);
  if (!files.length) return;
  $('uploadStatus').textContent = `Uploading ${files.length} file(s)…`;
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    await api('/api/tracks', { method: 'POST', body: form });
  }
  $('uploadStatus').textContent = 'Upload complete. Analysis is running.';
  await loadTracks();
}

async function scanImport() {
  $('uploadStatus').textContent = 'Scanning /import…';
  const result = await api('/api/import/scan', { method: 'POST' });
  $('uploadStatus').textContent = `Imported ${result.imported.length} track(s), skipped ${result.skipped_existing} existing and ${result.skipped_unsupported} unsupported file(s).`;
  await loadTracks();
}

async function sendCorrection(action) {
  if (!state.selected) return;
  const body = { action, time: $('audio').currentTime };
  state.selected = await api(`/api/tracks/${state.selected.id}/corrections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  renderDetail();
  await drawWaveform();
  await loadTracks();
}

$('uploadButton').addEventListener('click', uploadFiles);
$('scanImportButton').addEventListener('click', scanImport);
$('refreshButton').addEventListener('click', loadTracks);
$('settingsButton').addEventListener('click', () => { $('settingsPanel').hidden = false; loadServerSettings(); });
$('closeSettings').addEventListener('click', () => { $('settingsPanel').hidden = true; });
$('searchInput').addEventListener('input', renderTrackList);
$('showReviewed').addEventListener('change', (event) => { state.settings.showReviewed = event.target.checked; saveSettings(); renderTrackList(); });
$('sortSelect').addEventListener('change', (event) => { state.settings.sort = event.target.value; saveSettings(); renderTrackList(); });
$('themeSelect').addEventListener('change', (event) => { state.settings.theme = event.target.value; saveSettings(); drawWaveform(); });
$('accentInput').addEventListener('input', (event) => { state.settings.accent = event.target.value; saveSettings(); drawWaveform(); });
$('autoRefresh').addEventListener('change', (event) => { state.settings.autoRefresh = event.target.checked; saveSettings(); });
$('compactMode').addEventListener('change', (event) => { state.settings.compactMode = event.target.checked; saveSettings(); });
$('tagButton').addEventListener('click', async () => {
  if (!state.selected) return;
  await api(`/api/tracks/${state.selected.id}/write-tags`, { method: 'POST' });
  alert('BPM/comment tag written.');
});
document.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => sendCorrection(button.dataset.action)));
matchMedia('(prefers-color-scheme: light)').addEventListener('change', applySettings);
applySettings();
loadTracks();
