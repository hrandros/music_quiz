
/* static/js/admin_setup.js */

const SETUP = {};
let wavesurfer = null;
let wsRegions = null;
let currentEditingId = null;

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

// --- INIT ---

document.addEventListener("DOMContentLoaded", () => {
  try { SETUP.initWaveSurfer(); } catch (e) { console.error("WaveSurfer init error:", e); }

  // Sortable
  const el = document.getElementById('quizSongsList');
  if (el && typeof Sortable !== 'undefined') {
    Sortable.create(el, {
      animation: 150,
      handle: '.q-row',
      onEnd: function (evt) {
        // TODO: opcionalno spremi novi redoslijed na server
      }
    });
  }

  // Zadnja putanja iz localStorage
  const savedPath = localStorage.getItem('rockQuiz_lastPath');
  if (savedPath) {
    const input = document.getElementById('localFolderPath');
    if (input) {
      input.value = savedPath;
      SETUP.scanFolder(); // auto-scan
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

  // Sigurnost: ukloni prethodne handler-e ako postoje
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

  const btn = document.getElementById('btnPlayPause');
  if (btn) btn.onclick = () => wavesurfer.playPause();
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
      const du = parseFloat(dur || 15);
      wsRegions.addRegion({
        start: st,
        end: st + du,
        color: "rgba(211, 47, 47, 0.4)",
        drag: true,
        resize: true
      });
      wavesurfer.setTime(st);
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
  if (!t) return alert("Upiši naziv!");
  await fetch("/admin/create_quiz", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ title: t })
  });
  location.reload();
};

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
      btnAdd.onclick = (ev) => SETUP.importSong(ev, fullPath, fileNameWithExt);

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

// --- DODATNO: Dodavanje reda u desnu tablicu bez reload-a

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
    s.duration || 15
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