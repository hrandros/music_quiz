const SETUP = {};
let wavesurfer = null;
let wsRegions = null;
let currentEditingId = null;
// pixels per second zoom level (0 = fit)
SETUP._zoomPx = 0;

document.addEventListener('DOMContentLoaded', function () {
  if (typeof flatpickr !== 'undefined') {
    flatpickr('#newQuizDate', {
      altInput: true,
      altFormat: 'd.m.Y',
      dateFormat: 'Y-m-d',
      defaultDate: 'today',
      locale: 'hr',
      allowInput: true
    });
  }
});
// --- HELPERS ---

function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createEl(tag, cls, text) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text != null) el.textContent = text;
  return el;
}

function addSongToTableHTML(s) {
  const tbody = document.getElementById('quizSongsList');
  if (!tbody) { location.reload(); return; }

  const tr = document.createElement('tr');
  tr.className = 'q-row';
  tr.id = 'qrow-' + s.id;
  tr.dataset.round = s.round;

  const tdBadge = document.createElement('td');
  tdBadge.className = 'ps-3';
  tdBadge.style.width = '40px';
  tdBadge.innerHTML = `<span class="badge bg-warning text-dark">R${s.round}</span>`;

  const tdText = document.createElement('td');
  const artistDiv = createEl('div', 'fw-bold text-white text-truncate', s.artist || '');
  artistDiv.style.maxWidth = '250px';
  const titleDiv = createEl('div', 'small text-muted text-truncate', s.title || '');
  titleDiv.style.maxWidth = '250px';
  tdText.appendChild(artistDiv);
  tdText.appendChild(titleDiv);

  const tdAct = document.createElement('td');
  tdAct.className = 'text-end pe-3';
  tdAct.style.width = '100px';
  const group = createEl('div', 'btn-group');

  const btnEdit = createEl('button', 'btn btn-sm btn-outline-info');
  btnEdit.title = 'Uredi isječak';
  btnEdit.innerHTML = '<i class="bi bi-pencil-fill"></i>';
  btnEdit.onclick = () => SETUP.openEditor(
    s.id,
    s.filename || 'None',
    s.artist || '',
    s.title || '',
    s.start || 0,
    s.duration || 30
  );

  const btnDel = createEl('button', 'btn btn-sm btn-outline-danger');
  btnDel.title = 'Obriši iz kviza';
  btnDel.innerHTML = '<i class="bi bi-trash-fill"></i>';
  btnDel.onclick = () => SETUP.removeSong(s.id);

  group.appendChild(btnEdit);
  group.appendChild(btnDel);
  tdAct.appendChild(group);

  tr.appendChild(tdBadge);
  tr.appendChild(tdText);
  tr.appendChild(tdAct);
  tbody.appendChild(tr);
}

function openNewQuizModal() {
    if (window.SETUP?.closeEditor) SETUP.closeEditor();
    const el = document.getElementById('newQuizModal');
    if (el && el.parentNode !== document.body) {
      document.body.appendChild(el);
    }
    const modal = bootstrap.Modal.getOrCreateInstance(el); 
    modal.show();
  }

// Generiraj QR kodove za timove
function generateQR() {
  const text = document.getElementById('teamsInput').value;
  const cont = document.getElementById('qrPreview');
  cont.innerHTML = "";
  cont.classList.remove('d-none');
  const ip = location.hostname + ":5000";
  const style = document.createElement('style');
  style.innerHTML = `@media print {
    body * { visibility: hidden; }
    #qrPreview, #qrPreview * { visibility: visible; }
    #qrPreview { position: absolute; top:0; left:0; width:100%; display:block !important; }
    .qr-card { display:inline-block; border:1px solid #000; padding:20px; margin:10px; text-align:center; width: 40%; page-break-inside: avoid; }
  }`;
  document.head.appendChild(style);
  text.split('\n').forEach(line => {
    if (line.trim()) {
      const pin = Math.floor(1000 + Math.random() * 9000);
      const url = `http://${ip}/player?name=${encodeURIComponent(line.trim())}&pin=${pin}`;
      const div = document.createElement('div');
      div.className = 'qr-card';
      div.innerHTML = `<h2>${line}</h2><div id="qr-${pin}"></div><h3>PIN: ${pin}</h3>`;
      cont.appendChild(div);
      new QRCode(div.querySelector(`#qr-${pin}`), { text: url, width:128, height:128 });
    }
  });

  setTimeout(() => window.print(), 500);
}

  // Datepicker initialized in template with flatpickr (keeps ISO value, shows dd.mm.YYYY)

// --- INIT ---

document.addEventListener("DOMContentLoaded", () => {
  try { SETUP.initWaveSurfer(); } catch (e) { console.error("WaveSurfer init error:", e); }
  const el = document.getElementById('quizSongsList');
  if (el && typeof Sortable !== 'undefined') {
    Sortable.create(el, {
      animation: 150,
      handle: '.q-row',
      onEnd: function (evt) {
      }
    });
  }
  const savedPath = localStorage.getItem('rockQuiz_lastPath');
  if (savedPath) {
    const input = document.getElementById('localFolderPath');
    if (input) {
      input.value = savedPath;
      SETUP.scanFolder();
    }
  }
});

// --- WAVESURFER ---

SETUP.initWaveSurfer = function () {
  if (typeof WaveSurfer === 'undefined') return;
  if (wavesurfer) {
    try { wavesurfer.destroy(); } catch (_) {}
    wavesurfer = null;
  }
  wavesurfer = WaveSurfer.create({
    container: "#waveform",
    waveColor: '#666',
    progressColor: '#d32f2f',
    cursorColor: '#fff',
    height: 100,
    normalize: true,
    backend: 'MediaElement'
  });
  wavesurfer.un && wavesurfer.un('timeupdate');
  wavesurfer.on('timeupdate', (t) => {
    const lbl = document.getElementById('lblCurrent');
    if (lbl) lbl.innerText = t.toFixed(1) + 's';
  });
  wavesurfer.on('play', () => {
    const i = document.querySelector('#btnPlayPause i');
    if (i) i.className = 'bi bi-pause-fill';
  });
  wavesurfer.on('pause', () => {
    const i = document.querySelector('#btnPlayPause i');
    if (i) i.className = 'bi bi-play-fill';
  });
  const volSlider = document.getElementById('wsVolume');
  if (volSlider) {
    wavesurfer.setVolume(volSlider.value);
    volSlider.oninput = function () { wavesurfer.setVolume(this.value); };
  }
  if (window.WaveSurfer?.Regions) {
    wsRegions = wavesurfer.registerPlugin(window.WaveSurfer.Regions.create());
    wsRegions.on('region-updated', (region) => {
      const s = document.getElementById('lblStart');
      const d = document.getElementById('lblDur');
      if (s) s.innerText = region.start.toFixed(1);
      if (d) d.innerText = (region.end - region.start).toFixed(1);
    });
    wsRegions.on('region-clicked', (region, e) => {
      e.stopPropagation();
      region.play();
    });
  }
  try { SETUP.renderTimeMarks(); } catch (e) { /* ignore */ }
  const btn = document.getElementById('btnPlayPause');
  if (btn) btn.onclick = () => wavesurfer.playPause();
  // Zoom buttons
  const zin = document.getElementById('btnZoomIn');
  const zout = document.getElementById('btnZoomOut');
  const zreset = document.getElementById('btnZoomReset');
  if (zin) zin.onclick = () => SETUP.zoomIn();
  if (zout) zout.onclick = () => SETUP.zoomOut();
  if (zreset) zreset.onclick = () => SETUP.zoomReset();
};

// Zoom helpers
SETUP.setZoomPx = function(px) {
  SETUP._zoomPx = Math.max(0, px || 0);
  if (!wavesurfer) return;
  try {
    console.debug && console.debug('SETUP.setZoomPx', { requestedPx: px, effectivePx: SETUP._zoomPx, hasZoom: typeof(wavesurfer.zoom) === 'function' });
    if (typeof wavesurfer.zoom === 'function') {
      // wavesurfer.zoom expects pixels per second (v7)
      wavesurfer.zoom(SETUP._zoomPx);
      // After zoom, center view around selected region (if any) or current time
      try {
        const dur = wavesurfer.getDuration() || 0;
        if (dur > 0) {
          let centerTime = dur / 2;
          // If there's an active region, center on its midpoint
          // Prefer selected region, then stored song region
          let r = null;
          if (wsRegions) {
            const regions = Object.values(wsRegions.list || {});
            r = regions.find(rr => rr.selected) || regions[0];
          }
          if (r) {
            centerTime = (r.start + r.end) / 2;
          } else if (SETUP._currentSongRegion && SETUP._currentSongRegion.duration > 0) {
            centerTime = (SETUP._currentSongRegion.start + SETUP._currentSongRegion.duration) / 2;
          }
          // If no region, use currentTime if available
          try { const ct = wavesurfer.getCurrentTime(); if (ct) centerTime = ct; } catch (e) {}

          // Seek to center ratio; seekTo will also adjust scroll/viewport
          const ratio = Math.max(0, Math.min(1, centerTime / dur));
          // preserve paused state
          const wasPlaying = !wavesurfer.paused;
          wavesurfer.pause();
          wavesurfer.seekTo(ratio);

          // Best-effort center: compute total pixel width and scroll so centerTime is centered
          setTimeout(() => {
            try {
              const container = document.getElementById('waveform');
              const renderer = wavesurfer.drawer || wavesurfer.renderer || {};
              const wrapper = renderer && (renderer.wrapper || renderer.container || renderer.element);
              const totalWidth = wrapper ? (wrapper.scrollWidth || wrapper.offsetWidth) : (container ? container.clientWidth : 0);
              const centerPx = (ratio) * totalWidth;
              const visibleW = container ? container.clientWidth : 800;
              if (wrapper) wrapper.scrollLeft = Math.max(0, Math.floor(centerPx - visibleW / 2));
              // try to call renderer recenter if available
              try { if (typeof renderer.recenter === 'function') renderer.recenter(); } catch(e) {}
              // render time marks after zoom/resize
              try { SETUP.queueRenderMarks(); } catch (e) { /* ignore */ }
            } catch (e) { /* ignore */ }
          }, 50);
        }
      } catch (e) {
        console.warn('Center after zoom failed', e);
      }
    } else if (typeof wavesurfer.params !== 'undefined' && wavesurfer.params.partialRender) {
      // no-op fallback: try to redraw
      wavesurfer.drawer && wavesurfer.drawer.recenter && wavesurfer.drawer.recenter();
    } else {
      console.warn('WaveSurfer.zoom not available in this build');
    }
  } catch (e) {
    console.warn('Zoom error', e);
  }
};

SETUP.zoomIn = function() {
  console.debug && console.debug('SETUP.zoomIn called', { currentPx: SETUP._zoomPx });
  // If a region is selected, zoom to that region so it fills the viewport
  if (wsRegions) {
    const regions = Object.values(wsRegions.list || {});
    const sel = regions.find(r => r.selected) || regions[0];
    if (sel) {
      return SETUP.zoomToRegion(sel);
    }
  }
  // If no interactive region, but we have song clip info, zoom to that clip
  if (SETUP._currentSongRegion && SETUP._currentSongRegion.duration > 0) {
    return SETUP.zoomToClip(SETUP._currentSongRegion.start, SETUP._currentSongRegion.duration);
  }
  // Fallback incremental zoom
  const step = 40;
  const next = SETUP._zoomPx === 0 ? 40 : SETUP._zoomPx + step;
  SETUP.setZoomPx(next);
};

SETUP.zoomOut = function() {
  const step = 10;
  const next = Math.max(0, (SETUP._zoomPx - step));
  SETUP.setZoomPx(next);
};

SETUP.zoomReset = function() {
  // Reset to fit entire waveform
  if (!wavesurfer) return SETUP.setZoomPx(0);
  try {
    const dur = wavesurfer.getDuration() || 1;
    const container = document.getElementById('waveform');
    const width = container ? container.clientWidth : (wavesurfer.drawer && wavesurfer.drawer.wrapper ? wavesurfer.drawer.wrapper.clientWidth : 800);
    const defaultPx = Math.max(0, Math.floor(width / dur));
    SETUP.setZoomPx(defaultPx);
    // center on middle
    wavesurfer.seekTo(0.5);
  } catch (e) {
    SETUP.setZoomPx(0);
  }
};

SETUP.zoomToRegion = function(region) {
  console.debug && console.debug('SETUP.zoomToRegion', { start: region?.start, end: region?.end });
  if (!wavesurfer || !region) return;
  try {
    const dur = wavesurfer.getDuration() || 1;
    const clipDur = Math.max(0.001, (region.end - region.start));
    const container = document.getElementById('waveform');
    const width = container ? container.clientWidth : (wavesurfer.drawer && wavesurfer.drawer.wrapper ? wavesurfer.drawer.wrapper.clientWidth : 800);

    // add padding (10s each side) but clamp to song bounds
    const pad = 10; // seconds of padding on each side
    const paddedStart = Math.max(0, region.start - pad);
    const paddedEnd = Math.min(dur, region.end + pad);
    const paddedDur = Math.max(0.001, (paddedEnd - paddedStart));
    // pixels per second so that padded clip fills the container: width / paddedDur
    let pxPerSec = width / paddedDur;
    // cap px/sec to avoid extreme zoom values
    const MAX_PX_PER_SEC = 3000;
    pxPerSec = Math.min(pxPerSec, MAX_PX_PER_SEC);
    console.debug && console.debug('SETUP.zoomToRegion pxPerSec', { width, paddedDur, pxPerSec, MAX_PX_PER_SEC });
    if (typeof wavesurfer.zoom === 'function') {
      wavesurfer.zoom(pxPerSec);
    }
    const centerTime = (paddedStart + paddedEnd) / 2;
    const ratio = Math.max(0, Math.min(1, centerTime / dur));
    // Seek to center without resuming playback
    const wasPlaying = !wavesurfer.paused;
    wavesurfer.pause();
    wavesurfer.seekTo(ratio);
    if (wasPlaying) { /* keep paused to avoid autoplay */ }
    // store current zoom px
    SETUP._zoomPx = pxPerSec;
    // adjust scroll to center region visually
    setTimeout(() => {
      try {
        const renderer = wavesurfer.drawer || wavesurfer.renderer || {};
        const wrapper = renderer && (renderer.wrapper || renderer.container || renderer.element);
        const container = document.getElementById('waveform');
        const totalWidth = wrapper ? (wrapper.scrollWidth || wrapper.offsetWidth) : (container ? container.clientWidth : 0);
        const centerPx = Math.max(0, Math.min(totalWidth, (ratio) * totalWidth));
        const visibleW = container ? container.clientWidth : 800;
        if (wrapper) wrapper.scrollLeft = Math.max(0, Math.floor(centerPx - visibleW / 2));
        try { if (typeof renderer.recenter === 'function') renderer.recenter(); } catch(e) {}
        // refresh marks after scrolling/zoom
        try { SETUP.queueRenderMarks(); } catch (e) {}
      } catch (e) {}
    }, 50);
  } catch (e) {
    console.warn('zoomToRegion failed', e);
  }
};

SETUP.zoomToClip = function(start, clipDur) {
  if (!wavesurfer) return;
  try {
    const dur = wavesurfer.getDuration() || 1;
    const container = document.getElementById('waveform');
    const width = container ? container.clientWidth : (wavesurfer.drawer && wavesurfer.drawer.wrapper ? wavesurfer.drawer.wrapper.clientWidth : 800);
    // add padding (10s each side) but clamp to song bounds
    const pad = 10;
    const paddedStart = Math.max(0, start - pad);
    const paddedEnd = Math.min(dur, start + (clipDur || 0) + pad);
    const paddedDur = Math.max(0.001, (paddedEnd - paddedStart));
    let pxPerSec = width / paddedDur;
    const MAX_PX_PER_SEC = 3000;
    pxPerSec = Math.min(pxPerSec, MAX_PX_PER_SEC);
    console.debug && console.debug('SETUP.zoomToClip pxPerSec', { width, paddedDur, pxPerSec, MAX_PX_PER_SEC });
    if (typeof wavesurfer.zoom === 'function') wavesurfer.zoom(pxPerSec);

    const centerTime = paddedStart + paddedDur / 2;
    const ratio = Math.max(0, Math.min(1, centerTime / dur));
    const wasPlaying = !wavesurfer.paused;
    wavesurfer.pause();
    wavesurfer.seekTo(ratio);
    if (wasPlaying) { }
    SETUP._zoomPx = pxPerSec;
    setTimeout(() => {
      try {
        const renderer = wavesurfer.drawer || wavesurfer.renderer || {};
        const wrapper = renderer && (renderer.wrapper || renderer.container || renderer.element);
        const totalWidth = wrapper ? (wrapper.scrollWidth || wrapper.offsetWidth) : (container ? container.clientWidth : 0);
        const centerPx = Math.max(0, Math.min(totalWidth, ratio * totalWidth));
        const visibleW = container ? container.clientWidth : 800;
        if (wrapper) wrapper.scrollLeft = Math.max(0, Math.floor(centerPx - visibleW / 2));
        try { if (typeof renderer.recenter === 'function') renderer.recenter(); } catch(e) {}
        // refresh marks after scrolling/zoom
        try { SETUP.queueRenderMarks(); } catch (e) {}
      } catch (e) {}
    }, 50);
  } catch (e) { console.warn('zoomToClip failed', e); }
};

// --- EDITOR ---

SETUP.openEditor = function (id, filename, artist, title, start, dur) {
  if (!filename || filename === 'None') {
    alert("Ovo nije audio pitanje (nema MP3).");
    return;
  }
  if (!wavesurfer) SETUP.initWaveSurfer();
  currentEditingId = id;
  const panel = document.getElementById('editorPanel');
  if (panel) panel.style.display = 'block';
  document.getElementById('editId').value = id;
  document.getElementById('editArtist').value = artist || '';
  document.getElementById('editTitle').value = title || '';
  document.querySelectorAll('.q-row').forEach(r => r.classList.remove('editing-row'));
  const row = document.getElementById('qrow-' + id);
  if (row) row.classList.add('editing-row');
  wavesurfer.load('/stream_song/' + filename);

  // osiguraj da 'ready' handler postoji samo jednom
  wavesurfer.once('ready', () => {
    if (wsRegions) {
      wsRegions.clearRegions();
      const st = parseFloat(start || 0);
      const du = parseFloat(dur || 30);
      wsRegions.addRegion({
        start: st,
        end: st + du,
        color: "rgba(211, 47, 47, 0.4)",
        drag: true,
        resize: true
      });
      wavesurfer.setTime(st);
      // render time marks (every 10s)
      try { SETUP.queueRenderMarks(); } catch (e) { /* ignore */ }
    }
  });

  wavesurfer.once('error', (e) => {
    console.error("WaveSurfer error:", e);
    alert("Ne mogu učitati pjesmu: " + filename);
  });
};

SETUP.closeEditor = function () {
  const panel = document.getElementById('editorPanel');
  if (panel) panel.style.display = 'none';
  if (wavesurfer) wavesurfer.pause();
  document.querySelectorAll('.q-row').forEach(r => r.classList.remove('editing-row'));
};

SETUP.saveChanges = async function () {
  if (!currentEditingId) return;
  const artist = document.getElementById('editArtist').value;
  const title = document.getElementById('editTitle').value;

  let start = 0, duration = 15;
  if (wsRegions) {
    const regions = wsRegions.getRegions();
    if (regions.length > 0) {
      start = regions[0].start;
      duration = regions[0].end - regions[0].start;
    }
  }
  try {
    const res = await fetch("/admin/update_song", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        id: currentEditingId,
        artist: artist,
        title: title,
        start: start,
        duration: duration
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      location.reload();
    } else {
      alert("Greška pri spremanju!");
    }
  } catch (e) {
    console.error(e);
    alert("Greška: Provjeri postoji li ruta /admin/update_song u backendu.");
  }
};


// --- MANIPULACIJA PJESMAMA ---

SETUP.removeSong = async function (id) {
  if (!confirm("Obrisati?")) return;
  await fetch("/admin/remove_song", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id })
  });
  location.reload();
};

SETUP.createNewQuiz = async function () {
  const t = document.getElementById('newQuizTitle').value;
  const d = document.getElementById('newQuizDate').value;
  if (!t) return alert("Upiši naziv!");
  await fetch("/admin/create_quiz", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ title: t, date: d })
  });
  location.reload();
};

SETUP.switchQuiz = async function (id) {
  await fetch("/admin/switch_quiz", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ id })
  });
  location.reload();
}

SETUP.filterView = function (round, btn) {
  // vizualno
  document.querySelectorAll('.btn-group .btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const r = parseInt(round, 10);
  document.querySelectorAll('.q-row').forEach(row => {
    const rowR = parseInt(row.dataset.round, 10);
    row.style.display = (r === 0 || rowR === r) ? 'table-row' : 'none';
  });
};

// --- FS / SCAN / IMPORT ---

let scanning = false;

SETUP.scanFolder = async function () {
  if (scanning) return;
  const pathInput = document.getElementById('localFolderPath');
  const listContainer = document.getElementById('repoFileList');

  const path = (pathInput?.value || "").trim();
  if (!path) {
    alert("Molimo unesite putanju do mape!");
    return;
  }

  localStorage.setItem('rockQuiz_lastPath', path);
  scanning = true;
  listContainer.innerHTML = '<div class="p-3 text-center text-muted">Tražim…</div>';

  try {
    const res = await fetch("/admin/scan_local_folder", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ path })
    });
    const data = await res.json();

    if (data.status === 'error') {
      listContainer.innerHTML = `<div class="p-3 text-danger">${escapeHtml(data.msg)}</div>`;
      return;
    }
    if (!data.files || data.files.length === 0) {
      listContainer.innerHTML = '<div class="p-3 text-muted">Nema MP3 datoteka u ovoj mapi.</div>';
      return;
    }

    // Sigurniji render (bez innerHTML konkatenacije)
    listContainer.innerHTML = "";
    data.files.forEach(f => {
      const fullPath = (path.endsWith('/') || path.endsWith('\\')) ? (path + f) : (path + '/' + f);
      const fileNameWithExt = f.split('/').pop();
      const displayName = (fileNameWithExt || '').replace(/\.mp3$/i, '');

      const row = createEl('div', 'list-group-item d-flex align-items-center justify-content-between');
      const left = createEl('div', 'text-truncate');
      const strong = createEl('div', 'fw-bold text-white text-truncate', displayName);
      strong.title = displayName;
      const small = createEl('div', 'small text-muted text-truncate', f);
      left.appendChild(strong);
      left.appendChild(small);

      const btns = createEl('div', 'btn-group btn-group-sm');
      const btnAdd = createEl('button', 'btn btn-success', '+');
      btnAdd.title = 'Dodaj u kviz';
      btnAdd.onclick = (ev) => SETUP.showImportModal(ev, fullPath, fileNameWithExt);

      const btnMeta = createEl('button', 'btn btn-outline-info', 'Meta');
      btnMeta.title = 'Pokušaj dohvatiti izvođača/naslov (Deezer)';
      btnMeta.onclick = (ev) => SETUP.magicCheck(ev, fullPath, fileNameWithExt);

      btns.appendChild(btnAdd);
      btns.appendChild(btnMeta);

      row.appendChild(left);
      row.appendChild(btns);
      listContainer.appendChild(row);
    });

  } catch (e) {
    console.error(e);
    listContainer.innerHTML = '<div class="p-3 text-danger">Greška pri skeniranju.</div>';
  } finally {
    scanning = false;
  }
};

SETUP.importSong = async function (ev, fullPath, filename, artist = "", title = "") {
  const btn = ev?.currentTarget || null;
  const original = btn ? btn.innerHTML : "";
  const rEl = document.getElementById('targetRound');
  const r = rEl ? rEl.value : 1;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
  }

  try {
    const res = await fetch("/admin/import_external_song", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        source_path: fullPath,
        filename: filename,
        round: r,
        artist: artist,
        title: title
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      if (btn) {
        btn.classList.remove('btn-success');
        btn.classList.add('btn-outline-success');
        btn.innerHTML = '<i class="bi bi-check-lg"></i>';
      }
      addSongToTableHTML(data.song);
      const emptyMsg = document.querySelector('.table-container .text-center');
      if (emptyMsg) emptyMsg.style.display = 'none';
    } else {
      alert("Greška: " + (data.msg || 'Neuspješno'));
      if (btn) {
        btn.innerHTML = original;
        btn.disabled = false;
      }
    }
  } catch (e) {
    console.error(e);
    if (btn) {
      btn.innerHTML = original;
      btn.disabled = false;
    }
  }
};

SETUP.openPicker = async function (ev) {
  const btn = ev?.currentTarget;
  const oldIcon = btn ? btn.innerHTML : '';

  if (btn) {
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;
  }
  try {
    const res = await fetch("/admin/open_folder_picker");
    const data = await res.json();
    if (data.status === 'ok' && data.path) {
      const input = document.getElementById('localFolderPath');
      if (input) input.value = data.path;
      localStorage.setItem('rockQuiz_lastPath', data.path);
      SETUP.scanFolder();
    }
  } catch (e) {
    console.error("Greška pri otvaranju pickera:", e);
  } finally {
    if (btn) {
      btn.innerHTML = oldIcon;
      btn.disabled = false;
    }
  }
};

SETUP.magicCheck = async function (ev, fullPath, filename) {
  const btn = ev?.currentTarget;
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;
  }
  try {
    const res = await fetch("/admin/api_check_deezer", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ filename: filename })
    });
    const data = await res.json();
    if (data.status === "ok" && data.found) {
      if (confirm(`Pronađeno:\n\nIzvođač: ${data.artist}\nNaslov: ${data.title}\n\nUvesti s ovim podacima?`)) {
        await SETUP.importSong(ev, fullPath, filename, data.artist, data.title);
      }
    } else {
      alert("Deezer nije pronašao podatke za: " + filename);
    }
  } catch (e) {
    console.error(e);
    alert("Greška u komunikaciji s Deezerom.");
  } finally {
    if (btn) {
      btn.innerHTML = oldHtml;
      btn.disabled = false;
    }
  }
};

// Show modal to enter artist/title before importing
SETUP.showImportModal = function (ev, fullPath, filename) {
  SETUP._pendingImport = { ev, fullPath, filename };
  const modalEl = document.getElementById('importSongModal');
  if (!modalEl) {
    // fallback: call import directly
    return SETUP.importSong(ev, fullPath, filename);
  }
  const fnInput = document.getElementById('importFilename');
  const artistInput = document.getElementById('importArtist');
  const titleInput = document.getElementById('importTitle');
  if (fnInput) fnInput.value = filename;
  if (artistInput) artistInput.value = '';
  if (titleInput) titleInput.value = filename.replace(/\.mp3$/i, '').replace(/[_\-]/g, ' ');

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
};

SETUP.confirmImport = async function () {
  const pending = SETUP._pendingImport;
  if (!pending) return;
  const artist = (document.getElementById('importArtist')?.value || '').trim();
  const title = (document.getElementById('importTitle')?.value || '').trim();
  const modalEl = document.getElementById('importSongModal');
  const modal = modalEl ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;
  try {
    await SETUP.importSong(pending.ev, pending.fullPath, pending.filename, artist, title);
  } finally {
    SETUP._pendingImport = null;
    if (modal) modal.hide();
  }
};

// --- HELPERI ZA WAVESURFER DOM I PX/SEC ---

SETUP._getWaveElements = function () {
  const container = document.getElementById('waveform');
  let renderer = null, wrapper = null;

  if (wavesurfer) {
    // v7 renderer
    if (wavesurfer.renderer) {
      renderer = wavesurfer.renderer;
      try {
        if (typeof renderer.getWrapper === 'function') {
          wrapper = renderer.getWrapper();
        } else if (renderer.elements && renderer.elements.wrapper) {
          wrapper = renderer.elements.wrapper;
        } else if (renderer.wrapper || renderer.container || renderer.element) {
          wrapper = renderer.wrapper || renderer.container || renderer.element;
        }
      } catch (_) {}
    }
    // stariji v5/v6 drawer fallback
    if (!wrapper && wavesurfer.drawer) {
      renderer = wavesurfer.drawer;
      wrapper = wavesurfer.drawer.wrapper || wavesurfer.drawer.container || null;
    }
  }
  return { container, renderer, wrapper };
};

SETUP._getPxPerSec = function (dur) {
  const { container } = SETUP._getWaveElements();
  // Ako je postavljen zoomPx, koristi njega; inače „fit to width“
  if (SETUP._zoomPx && SETUP._zoomPx > 0) return SETUP._zoomPx;
  const cw = container ? container.clientWidth : 0;
  return dur > 0 && cw > 0 ? cw / dur : 0;
};

// Debounce preko RAF-a da se markeri crtaju tek kad DOM završi reflow
SETUP.queueRenderMarks = function () {
  if (SETUP._marksRaf) cancelAnimationFrame(SETUP._marksRaf);
  SETUP._marksRaf = requestAnimationFrame(() => {
    try { SETUP.renderTimeMarks(); } catch (e) {}
  });
};

// Draw time markers (every 10s) inside WaveSurfer wrapper
// Zamijeni postojeću implementaciju ovime:
SETUP.renderTimeMarks = function () {
  if (!wavesurfer) return;
  try {
    const dur = wavesurfer.getDuration() || 0;
    if (dur <= 0) return;

    const { container, wrapper } = SETUP._getWaveElements();
    const host = (wrapper || container);
    if (!host) return;

    const hostPos = window.getComputedStyle(host).position;
    if (!hostPos || hostPos === 'static') host.style.position = 'relative';

    // Osiguraj kontejner za markere
    let marksContainer = host.querySelector('.ws-time-marks');
    if (!marksContainer) {
      marksContainer = document.createElement('div');
      marksContainer.className = 'ws-time-marks';
      host.appendChild(marksContainer);
    }

    // Izračun pouzdane širine vremenske osi
    const pxPerSec = SETUP._getPxPerSec(dur);
    // totalWidth barem koliko je vidljiva širina kontejnera (za "fit to width")
    const visibleW = container ? container.clientWidth : (host.clientWidth || 0);
    const computedWidth = Math.max(visibleW, Math.floor(dur * pxPerSec));
    marksContainer.style.width = computedWidth + 'px';

    // Priprema vidljivog prozora za odlučivanje o labelama
    const visibleLeft = wrapper ? wrapper.scrollLeft : (container ? container.scrollLeft : 0);

    // Očisti prethodne markere
    marksContainer.innerHTML = '';

    const step = 10; // svake 10s
    const minLabelPx = 60;
    let lastLabelPx = -Infinity;

    for (let t = 0; t <= Math.ceil(dur); t += step) {
      const leftPx = Math.floor(t * pxPerSec);
      const mark = document.createElement('div');
      mark.className = 'ws-time-mark';
      mark.style.position = 'absolute';
      mark.style.left = leftPx + 'px';
      mark.style.top = '0';
      mark.style.height = '100%';
      mark.style.borderLeft = '1px solid rgba(255,255,255,0.18)';
      mark.style.pointerEvents = 'none';
      marksContainer.appendChild(mark);

      // Labelu renderiraj samo kad ima mjesta i kad je u vidljivom području (+/-20px margina)
      if (
        leftPx >= (visibleLeft - 20) &&
        leftPx <= (visibleLeft + visibleW + 20) &&
        Math.abs(leftPx - lastLabelPx) >= minLabelPx
      ) {
        const lbl = document.createElement('div');
        lbl.className = 'ws-time-label';
        lbl.style.position = 'absolute';
        lbl.style.top = '0';
        lbl.style.left = '0';
        lbl.style.transform = 'translateX(-50%)';
        lbl.style.minWidth = '44px';
        lbl.style.color = 'rgba(255,255,255,0.95)';
        lbl.style.fontSize = '11px';
        lbl.style.textAlign = 'center';
        lbl.style.pointerEvents = 'none';
        //lbl.style.background = 'rgba(0,0,0,0.75)';
        //lbl.style.padding = '2px 6px';
        //lbl.style.borderRadius = '4px';
        lbl.style.whiteSpace = 'nowrap';
        const mm = Math.floor(t / 60).toString().padStart(2, '0');
        const ss = Math.floor(t % 60).toString().padStart(2, '0');
        lbl.textContent = `${mm}:${ss}`;
        mark.appendChild(lbl);
        lastLabelPx = leftPx;
      }
    }

    // Scroll listener (jednom) da labelice prate pomak
    if (wrapper && !marksContainer._hasScrollListener) {
      marksContainer._hasScrollListener = true;
      wrapper.addEventListener('scroll', function () {
        if (marksContainer._scrollTimer) clearTimeout(marksContainer._scrollTimer);
        marksContainer._scrollTimer = setTimeout(() => {
          try { SETUP.renderTimeMarks(); } catch (e) {}
        }, 50);
      });
    }
  } catch (e) {
    console.warn('renderTimeMarks failed', e);
  }
};

// update marks on window resize so positions stay correct
window.addEventListener('resize', function () {
  try { SETUP.queueRenderMarks(); } catch (e) {}
});