const state = {
  tracks: [],
  selected: null,
  waveformTrackId: null,
  audioContext: null,
  analyser: null,
  mediaSource: null,
  lowFilter: null,
  midFilter: null,
  highFilter: null,
  visualizerFrame: null,
  phraseLoop: false,
  loopStart: null,
  loopEnd: null,
};
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(await res.text());
  return res.headers.get('content-type')?.includes('application/json') ? res.json() : res.text();
}

function pct(value) { return value == null ? '—' : `${Math.round(value * 100)}%`; }
function secs(value) { return value == null ? '—' : `${Number(value).toFixed(3)}s`; }
function mmss(value) {
  if (!Number.isFinite(value)) return '0:00';
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function activeAnalysis() { return state.selected?.corrected_analysis || state.selected?.raw_analysis; }

async function loadBuildInfo() {
  try {
    const info = await api('/api/health');
    const sha = info.git_sha && info.git_sha !== 'unknown' ? ` · ${info.git_sha.slice(0, 7)}` : '';
    const build = info.build_tag && info.build_tag !== 'local' ? ` · ${info.build_tag}` : '';
    $('versionBadge').textContent = `${info.version}${sha}${build}`;
    $('versionBadge').title = `Git SHA: ${info.git_sha}\nBuild date: ${info.build_date}`;
  } catch (error) {
    $('versionBadge').textContent = 'version unavailable';
  }
}

async function loadTracks() {
  state.tracks = await api('/api/tracks');
  renderTrackList();
}

function renderTrackList() {
  const list = $('trackList');
  list.innerHTML = '';
  if (!state.tracks.length) {
    list.innerHTML = '<p class="empty">No tracks uploaded yet.</p>';
    return;
  }
  state.tracks.forEach((track) => {
    const card = document.createElement('button');
    card.className = `track-card ${state.selected?.id === track.id ? 'active' : ''}`;
    card.innerHTML = `
      <strong>${track.filename}</strong>
      <p>${track.status} · review: ${track.review_status}</p>
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
  state.waveformTrackId = null;
  state.phraseLoop = false;
  state.loopStart = null;
  state.loopEnd = null;
  $('loopPhrase').classList.remove('active');
  renderTrackList();
  renderDetail();
  await drawWaveform();
  drawPlaybackOverlay();
}

function renderDetail() {
  $('emptyState').hidden = true;
  $('trackDetail').hidden = false;
  $('detailTitle').textContent = state.selected.filename;
  $('audio').src = `/api/tracks/${state.selected.id}/audio`;
  $('jsonExport').href = `/api/tracks/${state.selected.id}/exports/analysis.json`;
  $('beatExport').href = `/api/tracks/${state.selected.id}/exports/beats.csv`;
  const analysis = activeAnalysis();
  const conf = analysis?.confidence || {};
  $('bpmInput').value = analysis?.bpm ?? '';
  $('metrics').innerHTML = [
    ['BPM', analysis?.bpm ?? '—'],
    ['Half display', analysis?.bpm_display_half ?? '—'],
    ['Candidate 1', secs(analysis?.candidate_salsa_1)],
    ['Candidate 5', secs(analysis?.candidate_salsa_5)],
    ['Analyzer', analysis?.analyzer ?? state.selected.status],
    ['BPM confidence', pct(conf.bpm)],
    ['Grid confidence', pct(conf.grid)],
    ['Downbeat confidence', pct(conf.downbeat)],
    ['Salsa 1 confidence', pct(conf.salsa_one)],
  ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');
  $('warnings').innerHTML = (analysis?.warnings || []).map((w) => `<p>⚠️ ${w}</p>`).join('');
}

function resizeCanvasToDisplay(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = Math.round(canvas.clientWidth * ratio);
  const height = Math.round(canvas.clientHeight * ratio);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return ratio;
}

async function drawWaveform() {
  const canvas = $('waveform');
  const ctx = canvas.getContext('2d');
  const ratio = resizeCanvasToDisplay(canvas);
  const analysis = activeAnalysis();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#0b0e14';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!state.selected) return;
  try {
    const audioData = await fetch(`/api/tracks/${state.selected.id}/audio`).then((r) => r.arrayBuffer());
    const audioCtx = new AudioContext();
    const audioBuffer = await audioCtx.decodeAudioData(audioData.slice(0));
    const data = audioBuffer.getChannelData(0);
    const step = Math.ceil(data.length / canvas.width);
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, '#4dd4ff');
    gradient.addColorStop(0.52, '#7d8799');
    gradient.addColorStop(1, '#ff4d6d');
    ctx.strokeStyle = gradient;
    ctx.lineWidth = Math.max(1, ratio);
    ctx.beginPath();
    for (let x = 0; x < canvas.width; x++) {
      let min = 1, max = -1;
      for (let i = 0; i < step; i++) {
        const datum = data[(x * step) + i] || 0;
        min = Math.min(min, datum); max = Math.max(max, datum);
      }
      ctx.moveTo(x, (1 + min) * canvas.height / 2);
      ctx.lineTo(x, (1 + max) * canvas.height / 2);
    }
    ctx.stroke();
    state.waveformTrackId = state.selected.id;
    audioCtx.close();
  } catch (error) {
    ctx.fillStyle = '#aeb7c8';
    ctx.font = `${14 * ratio}px sans-serif`;
    ctx.fillText('Waveform preview unavailable in this browser for this codec.', 24 * ratio, 42 * ratio);
  }
  drawMarkers(canvas, ctx, analysis);
}

function drawMarkers(canvas, ctx, analysis) {
  if (!analysis?.beats?.length || !analysis.duration) return;
  const ratio = window.devicePixelRatio || 1;
  ctx.font = `${11 * ratio}px sans-serif`;
  for (const beat of analysis.beats) {
    const x = (beat.time / analysis.duration) * canvas.width;
    ctx.strokeStyle = beat.is_salsa_1 ? '#ff4d6d' : beat.is_salsa_5 ? '#4dd4ff' : 'rgba(255,255,255,.28)';
    ctx.lineWidth = (beat.is_salsa_1 || beat.is_salsa_5 ? 2 : 1) * ratio;
    ctx.beginPath();
    ctx.moveTo(x, beat.is_downbeat ? 0 : 42 * ratio);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
    if (beat.is_salsa_1 || beat.is_salsa_5) {
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fillText(String(beat.count8), x + 3 * ratio, 18 * ratio);
    }
  }
}

function drawPlaybackOverlay() {
  const canvas = $('playheadCanvas');
  const ctx = canvas.getContext('2d');
  resizeCanvasToDisplay(canvas);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const audio = $('audio');
  const duration = activeAnalysis()?.duration || audio.duration;
  if (!duration || !Number.isFinite(duration)) return;
  const x = (audio.currentTime / duration) * canvas.width;
  ctx.strokeStyle = '#ffd166';
  ctx.lineWidth = 2 * (window.devicePixelRatio || 1);
  ctx.beginPath();
  ctx.moveTo(x, 0);
  ctx.lineTo(x, canvas.height);
  ctx.stroke();
  ctx.fillStyle = 'rgba(255, 209, 102, .18)';
  ctx.fillRect(Math.max(0, x - 3), 0, 6, canvas.height);
  $('playbackReadout').textContent = `${mmss(audio.currentTime)} / ${mmss(audio.duration || duration)}`;
}

function updateEqFilters() {
  if (!state.lowFilter || !state.midFilter || !state.highFilter) return;
  state.lowFilter.gain.value = Number($('eqLow').value);
  state.midFilter.gain.value = Number($('eqMid').value);
  state.highFilter.gain.value = Number($('eqHigh').value);
}

function setupVisualizer() {
  const audio = $('audio');
  try {
    if (!state.audioContext) {
      state.audioContext = new AudioContext();
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 1024;
      state.analyser.smoothingTimeConstant = 0.58;
      state.lowFilter = state.audioContext.createBiquadFilter();
      state.lowFilter.type = 'lowshelf';
      state.lowFilter.frequency.value = 180;
      state.midFilter = state.audioContext.createBiquadFilter();
      state.midFilter.type = 'peaking';
      state.midFilter.frequency.value = 1200;
      state.midFilter.Q.value = 0.9;
      state.highFilter = state.audioContext.createBiquadFilter();
      state.highFilter.type = 'highshelf';
      state.highFilter.frequency.value = 6000;
      state.mediaSource = state.audioContext.createMediaElementSource(audio);
      state.mediaSource.connect(state.lowFilter);
      state.lowFilter.connect(state.midFilter);
      state.midFilter.connect(state.highFilter);
      state.highFilter.connect(state.analyser);
      state.analyser.connect(state.audioContext.destination);
      updateEqFilters();
    }
    if (state.audioContext.state === 'suspended') state.audioContext.resume();
    $('eqStatus').textContent = 'live audio';
    if (!state.visualizerFrame) renderVisualizer();
  } catch (error) {
    $('eqStatus').textContent = 'EQ unavailable';
    console.error(error);
  }
}

function bandLevel(buffer, from, to) {
  const start = Math.max(0, Math.floor(buffer.length * from));
  const end = Math.max(start + 1, Math.floor(buffer.length * to));
  let peak = 0;
  for (let index = start; index < end; index++) peak = Math.max(peak, buffer[index] || 0);
  return peak / 255;
}

function renderVisualizer() {
  const canvas = $('eqCanvas');
  const ctx = canvas.getContext('2d');
  resizeCanvasToDisplay(canvas);
  const analyser = state.analyser;
  const buffer = new Uint8Array(analyser?.frequencyBinCount || 0);
  const draw = () => {
    state.visualizerFrame = requestAnimationFrame(draw);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#0b0e14';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!analyser) return;
    analyser.getByteFrequencyData(buffer);
    const low = bandLevel(buffer, 0.0, 0.08);
    const mid = bandLevel(buffer, 0.08, 0.38);
    const high = bandLevel(buffer, 0.38, 1.0);
    $('meterLow').style.transform = `scaleX(${low.toFixed(3)})`;
    $('meterMid').style.transform = `scaleX(${mid.toFixed(3)})`;
    $('meterHigh').style.transform = `scaleX(${high.toFixed(3)})`;
    $('eqStatus').textContent = `live L${Math.round(low * 100)} M${Math.round(mid * 100)} H${Math.round(high * 100)}`;
    const bars = 72;
    const gap = 2 * (window.devicePixelRatio || 1);
    const barWidth = (canvas.width - gap * (bars - 1)) / bars;
    for (let i = 0; i < bars; i++) {
      const start = Math.floor((i / bars) ** 1.65 * buffer.length);
      const end = Math.max(start + 1, Math.floor(((i + 1) / bars) ** 1.65 * buffer.length));
      let sum = 0;
      for (let bin = start; bin < end; bin++) sum += buffer[bin] || 0;
      const level = sum / (end - start) / 255;
      const boosted = Math.min(1, level * 1.8);
      const height = Math.max(2, boosted * canvas.height * 0.95);
      const x = i * (barWidth + gap);
      const y = canvas.height - height;
      const hue = 185 + (i / bars) * 180;
      ctx.fillStyle = `hsl(${hue} 95% ${45 + boosted * 28}%)`;
      ctx.fillRect(x, y, barWidth, height);
      ctx.fillStyle = `hsla(${hue} 95% 70% / ${0.18 + boosted * 0.35})`;
      ctx.fillRect(x, Math.max(0, y - 5), barWidth, 4);
    }
  };
  draw();
}

async function uploadFiles(files = Array.from($('fileInput').files || [])) {
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

async function sendCorrection(action, extra = {}) {
  if (!state.selected) return;
  const body = { action, time: $('audio').currentTime, ...extra };
  state.selected = await api(`/api/tracks/${state.selected.id}/corrections`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  renderDetail();
  await drawWaveform();
  drawPlaybackOverlay();
  await loadTracks();
}

function nearestBeat(direction) {
  const beats = activeAnalysis()?.beat_times || [];
  const current = $('audio').currentTime;
  if (!beats.length) return current;
  if (direction < 0) return [...beats].reverse().find((time) => time < current - 0.03) ?? beats[0];
  return beats.find((time) => time > current + 0.03) ?? beats[beats.length - 1];
}

$('uploadButton').addEventListener('click', () => uploadFiles());
$('refreshButton').addEventListener('click', loadTracks);
$('reanalyzeButton').addEventListener('click', async () => {
  if (!state.selected) return;
  await api(`/api/tracks/${state.selected.id}/analyze`, { method: 'POST' });
  $('uploadStatus').textContent = `Re-analysis started for ${state.selected.filename}.`;
  await loadTracks();
});
$('tagButton').addEventListener('click', async () => {
  if (!state.selected) return;
  await api(`/api/tracks/${state.selected.id}/write-tags`, { method: 'POST' });
  alert('BPM/comment tag written.');
});
$('setBpmButton').addEventListener('click', () => sendCorrection('set_bpm', { bpm: Number($('bpmInput').value) }));
['eqLow', 'eqMid', 'eqHigh'].forEach((id) => $(id).addEventListener('input', updateEqFilters));
document.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => sendCorrection(button.dataset.action)));
$('audio').addEventListener('play', setupVisualizer);
$('audio').addEventListener('timeupdate', () => {
  drawPlaybackOverlay();
  if (state.phraseLoop && state.loopStart != null && state.loopEnd != null && $('audio').currentTime >= state.loopEnd) {
    $('audio').currentTime = state.loopStart;
  }
});
$('audio').addEventListener('loadedmetadata', drawPlaybackOverlay);
$('waveform').addEventListener('click', (event) => {
  const analysis = activeAnalysis();
  const duration = analysis?.duration || $('audio').duration;
  if (!duration) return;
  const rect = event.currentTarget.getBoundingClientRect();
  $('audio').currentTime = ((event.clientX - rect.left) / rect.width) * duration;
  drawPlaybackOverlay();
});
$('jumpPrev').addEventListener('click', () => { $('audio').currentTime = nearestBeat(-1); });
$('jumpNext').addEventListener('click', () => { $('audio').currentTime = nearestBeat(1); });
$('loopPhrase').addEventListener('click', () => {
  state.phraseLoop = !state.phraseLoop;
  const beats = activeAnalysis()?.beat_times || [];
  const start = nearestBeat(-1);
  const startIndex = beats.findIndex((time) => Math.abs(time - start) < 0.001);
  state.loopStart = start;
  state.loopEnd = beats[startIndex + 8] ?? null;
  $('loopPhrase').classList.toggle('active', state.phraseLoop);
});
['dragenter', 'dragover'].forEach((name) => $('dropZone').addEventListener(name, (event) => {
  event.preventDefault();
  $('dropZone').classList.add('dragging');
}));
['dragleave', 'drop'].forEach((name) => $('dropZone').addEventListener(name, (event) => {
  event.preventDefault();
  $('dropZone').classList.remove('dragging');
}));
$('dropZone').addEventListener('drop', (event) => uploadFiles(Array.from(event.dataTransfer.files || [])));
window.addEventListener('resize', async () => {
  if (state.selected) await drawWaveform();
  drawPlaybackOverlay();
});
setInterval(loadTracks, 10000);
loadBuildInfo();
loadTracks();
