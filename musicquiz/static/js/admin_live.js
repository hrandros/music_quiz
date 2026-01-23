
const socket = io();

// --- GLOBALNE VARIJABLE ---
let currentRound = 1;
let autoPlayActive = false;
let playQueue = [];
let currentQueueIndex = 0;
let autoplayTimeout = null;
let audioStopTimer = null;

window.LIVE = window.LIVE || {};

// --- SOCKET LISTENERS ---

// Server traži da pustimo audio
socket.on('play_audio', (data) => {
  const audio = document.getElementById('audioPlayer');
  if (audioStopTimer) clearTimeout(audioStopTimer);

  if (!audio) return;

  audio.src = data.url;
  audio.onloadedmetadata = function () {
    audio.currentTime = data.start || 0;
    const vol = document.getElementById('vol');
    if (vol) audio.volume = vol.value;
    audio.play().then(() => {
      audioStopTimer = setTimeout(() => audio.pause(), (data.duration || 15) * 1000);
    }).catch(err => console.error("Greška pri reprodukciji:", err));
  };
});

// FULL lista igrača
socket.on('admin_player_list_full', (players) => {
  renderPlayerList(players);
});

// Ažuriranje liste igrača
socket.on('admin_update_player_list', (players) => {
  renderPlayerList(players);
});

// Ažuriranje statusa pojedinca
socket.on('admin_single_player_update', (d) => {
  const dot = document.getElementById(`status-dot-${d.name}`);
  if (dot) updateStatusDot(dot, d.status);
});

// Potvrda locka pojedinog igrača
socket.on('admin_lock_confirmed', (d) => {
  const btn = document.getElementById(`btn-lock-${d.player}`);
  if (btn) {
    btn.classList.remove('btn-outline-danger');
    btn.classList.add('btn-danger');
    btn.innerHTML = '<i class="bi bi-lock-fill"></i>';
    btn.disabled = true;
  }
});

// Podaci za ocjenjivanje
socket.on('admin_receive_grading_data', (data) => {
  const playlist = document.getElementById('playlist-card');
  const grading = document.getElementById('grading-view');
  if (playlist && grading) {
    playlist.style.display = 'none';
    grading.style.display = 'block';
  }
  renderGradingTableServerShape(data);
});

// --- RENDER FUNKCIJE ---

function renderPlayerList(players) {
  const tbody = document.getElementById('playerListBody');
  const countBadge = document.getElementById('playerCount');
  if (!tbody) return;
  if (countBadge) countBadge.innerText = players.length;

  tbody.innerHTML = "";
  players.forEach(p => {
    const tr = document.createElement('tr');

    const tdStatus = document.createElement('td');
    tdStatus.style.width = '20px';
    const span = document.createElement('span');
    span.id = `status-dot-${p.name}`;
    span.className = 'd-inline-block rounded-circle';
    span.style.width = '10px';
    span.style.height = '10px';
    span.title = p.status;
    updateStatusDot(span, p.status);
    tdStatus.appendChild(span);

    const tdName = document.createElement('td');
    tdName.className = 'text-white fw-bold text-truncate';
    tdName.style.maxWidth = '150px';
    tdName.textContent = p.name;
    const small = document.createElement('div');
    small.className = 'text-muted';
    small.style.fontSize = '0.7em';
    small.textContent = `${p.score} bodova`;
    tdName.appendChild(small);

    const tdAct = document.createElement('td');
    tdAct.className = 'text-end';
    const btn = document.createElement('button');
    btn.id = `btn-lock-${p.name}`;
    btn.className = 'btn btn-xs btn-outline-danger';
    btn.title = 'Zabrani odgovaranje za ovu pjesmu';
    btn.innerHTML = '<i class="bi bi-slash-circle"></i>';
    btn.onclick = () => lockPlayer(p.name);
    tdAct.appendChild(btn);

    tr.appendChild(tdStatus);
    tr.appendChild(tdName);
    tr.appendChild(tdAct);
    tbody.appendChild(tr);
  });
}

function updateStatusDot(el, status) {
  el.className = "d-inline-block rounded-circle";
  if (status === 'active') el.classList.add('bg-success');
  else if (status === 'away') el.classList.add('bg-danger', 'animate__animated', 'animate__flash', 'animate__infinite');
  else el.classList.add('bg-secondary');
}

function lockPlayer(name) {
  const activeRow = document.querySelector('.song-row.table-active');
  if (!activeRow) {
    alert("Nijedna pjesma ne svira trenutno.");
    return;
  }
  const songId = activeRow.getAttribute('data-id');
  if (confirm(`Zabraniti unos timu "${name}" za ovu pjesmu?`)) {
    socket.emit('admin_lock_single_player', { player_name: name, song_id: songId });
  }
}

// --- RUNDE ---

function selectRound(r) {
  currentRound = parseInt(r, 10);
  document.querySelectorAll('.round-tab').forEach((btn, i) => {
    if (i + 1 === currentRound) {
      btn.classList.add('active', 'btn-danger');
      btn.classList.remove('btn-outline-light');
    } else {
      btn.classList.remove('active', 'btn-danger');
      btn.classList.add('btn-outline-light');
    }
  });

  document.querySelectorAll('.song-row').forEach(row => {
    const rr = parseInt(row.getAttribute('data-round'), 10);
    if (rr === currentRound) {
      row.style.display = 'table-row';
      row.classList.remove('hidden-round');
    } else {
      row.style.display = 'none';
      row.classList.add('hidden-round');
    }
  });

  // (opcionalno) javi serveru promjenu runde ako ti treba
  // socket.emit('admin_change_round', { round: currentRound });
}

// --- AUDIO & AUTOPLAY ---

function playSong(id) {
  document.querySelectorAll('.song-row').forEach(row => {
    row.classList.remove('table-active', 'border-warning', 'border-3');
    row.style.opacity = "1";
  });

  const row = document.getElementById('row-' + id);
  if (row) {
    row.classList.add('table-active', 'border-warning', 'border-3');
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const artist = row.getAttribute('data-artist');
    const title = row.getAttribute('data-title');
    const dj = document.getElementById('dj-console');
    if (dj) {
      dj.style.display = 'block';
      document.getElementById('np-artist').textContent = artist || '';
      document.getElementById('np-title').textContent = title || '';
    }
  }

  socket.emit('admin_play_song', { id: parseInt(id, 10) });
}

function stopMusic() {
  if (autoplayTimeout) clearTimeout(autoplayTimeout);
  if (audioStopTimer) clearTimeout(audioStopTimer);
  autoPlayActive = false;

  const btn = document.getElementById('btn-autoplay');
  if (btn) {
    btn.classList.replace('btn-danger', 'btn-outline-danger');
    btn.innerHTML = '<i class="bi bi-collection-play"></i> AUTOPLAY';
  }

  const audio = document.getElementById('audioPlayer');
  if (audio) audio.pause();
}

function toggleAutoplay() {
  autoPlayActive = !autoPlayActive;
  const btn = document.getElementById('btn-autoplay');

  if (autoPlayActive) {
    if (btn) {
      btn.classList.replace('btn-outline-danger', 'btn-danger');
      btn.innerHTML = '<i class="bi bi-stop-circle-fill"></i> STOP AUTOPLAY';
    }

    playQueue = [];
    const visibleRows = document.querySelectorAll('.song-row:not(.hidden-round)');
    if (visibleRows.length === 0) {
      alert("Nema pjesama u ovoj rundi!");
      autoPlayActive = false;
      if (btn) {
        btn.classList.replace('btn-danger', 'btn-outline-danger');
        btn.innerHTML = '<i class="bi bi-collection-play"></i> AUTOPLAY';
      }
      return;
    }

    visibleRows.forEach(row => {
      const id = row.id.replace('row-', '');
      playQueue.push(id);
    });

    currentQueueIndex = 0;
    playNextInQueue();
  } else {
    stopMusic();
  }
}

function playNextInQueue() {
  if (!autoPlayActive) return;

  if (currentQueueIndex >= playQueue.length) {
    stopMusic();
    alert("Kraj runde! Pokrećem zaključavanje…");
    startTimer(); // lokalni countdown + lock
    return;
  }

  const songId = playQueue[currentQueueIndex];
  const row = document.getElementById('row-' + songId);

  let duration = 15;
  if (row && row.getAttribute('data-duration')) {
    const d = parseFloat(row.getAttribute('data-duration'));
    if (!isNaN(d) && d > 0) duration = d;
  }

  playSong(songId);
  currentQueueIndex++;

  const waitTime = (duration * 1000) + 5000;
  if (autoplayTimeout) clearTimeout(autoplayTimeout);
  autoplayTimeout = setTimeout(() => {
    if (autoPlayActive) playNextInQueue();
  }, waitTime);
}

// --- TIMER / GRADING ---

function startTimer() {
  let sec = 30;
  const btn = document.querySelector('button[onclick="startTimer()"]');
  const originalText = btn ? btn.innerHTML : null;
  if (btn) btn.disabled = true;

  const interval = setInterval(() => {
    sec--;
    if (btn) btn.innerHTML = `<i class="bi bi-hourglass-split"></i> ${sec}s`;
    if (sec <= 0) {
      clearInterval(interval);
      if (btn && originalText != null) {
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
      // Nema 'admin_start_timer' na serveru – samo lockamo rundu
      socket.emit('admin_lock_round', { round: currentRound });
    }
  }, 1000);
}

// Otvara grading i traži podatke
window.LIVE.openGrading = function () {
  document.getElementById('playlist-card').style.display = 'none';
  const gView = document.getElementById('grading-view');
  gView.style.display = 'block';
  document.getElementById('gradingRoundNum').innerText = currentRound;
  document.getElementById('gradingBody').innerHTML =
    '<tr><td colspan="4" class="p-4 text-center"><div class="spinner-border text-info"></div> Učitavam odgovore…</td></tr>';

  socket.emit('admin_request_grading', { round: currentRound });
};

window.LIVE.closeGrading = function () {
  document.getElementById('grading-view').style.display = 'none';
  document.getElementById('playlist-card').style.display = 'block';
};

socket.on('admin_receive_grading_data', (data) => {
  renderGradingTableServerShape(data);
});

function renderGradingTableServerShape(data) {
  const tbody = document.getElementById('gradingBody');
  tbody.innerHTML = "";

  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-muted">Nema odgovora u ovoj rundi.</td></tr>';
    return;
  }

  // sort po song_index pa po imenu
  data.sort((a, b) => (a.song_index !== b.song_index ? a.song_index - b.song_index : a.player.localeCompare(b.player)));

  data.forEach(row => {
    const tr = document.createElement('tr');
    tr.className = 'align-middle';

    const tdIdx = document.createElement('td');
    tdIdx.className = 'fw-bold text-secondary';
    tdIdx.textContent = `#${row.song_index}`;

    const tdPlayer = document.createElement('td');
    tdPlayer.className = 'fw-bold text-info text-start text-truncate';
    tdPlayer.style.maxWidth = '120px';
    tdPlayer.title = row.player;
    tdPlayer.textContent = row.player;

    const tdArtist = document.createElement('td');
    tdArtist.className = 'text-start position-relative';
    tdArtist.innerHTML = `
      <div class="d-flex justify-content-between mb-1">
        <span class="text-white text-truncate" style="max-width:200px;" title="${(row.artist_guess || '-')}">${row.artist_guess || '<span class="text-muted">-</span>'}</span>
        ${generateScoreBtns(row.answer_id, 'artist', row.artist_pts)}
      </div>
      <div class="small text-success border-top border-secondary pt-1">
        <i class="bi bi-check-circle-fill me-1"></i> ${row.correct_artist}
      </div>`;

    const tdTitle = document.createElement('td');
    tdTitle.className = 'text-start position-relative';
    tdTitle.innerHTML = `
      <div class="d-flex justify-content-between mb-1">
        <span class="text-white text-truncate" style="max-width:200px;" title="${(row.title_guess || '-')}">${row.title_guess || '<span class="text-muted">-</span>'}</span>
        ${generateScoreBtns(row.answer_id, 'title', row.title_pts)}
      </div>
      <div class="small text-success border-top border-secondary pt-1">
        <i class="bi bi-check-circle-fill me-1"></i> ${row.correct_title}
      </div>`;

    tr.appendChild(tdIdx);
    tr.appendChild(tdPlayer);
    tr.appendChild(tdArtist);
    tr.appendChild(tdTitle);
    tbody.appendChild(tr);
  });
}

function generateScoreBtns(id, type, currentScore) {
  const is0 = currentScore === 0 ? 'active' : '';
  const is05 = currentScore === 0.5 ? 'active' : '';
  const is1 = currentScore === 1 ? 'active' : '';
  return `
    <div class="btn-group btn-group-sm score-group" role="group">
      <button type="button" class="btn btn-outline-danger ${is0}" onclick="LIVE.setScore(this, ${id}, '${type}', 0)">0</button>
      <button type="button" class="btn btn-outline-warning ${is05}" onclick="LIVE.setScore(this, ${id}, '${type}', 0.5)">½</button>
      <button type="button" class="btn btn-outline-success ${is1}" onclick="LIVE.setScore(this, ${id}, '${type}', 1)">1</button>
    </div>`;
}

window.LIVE.setScore = function (btn, ansId, type, val) {
  const group = btn.parentElement;
  group.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  socket.emit('admin_update_score', { answer_id: ansId, type: type, value: val });
};

window.LIVE.finalizeRound = function () {
  if (!confirm("Jeste li sigurni da želite zaključiti ocjenjivanje?\nOvo će ažurirati tablicu poretka.")) return;
  socket.emit('admin_finalize_round', { round: currentRound });
  window.LIVE.closeGrading();
  alert("Rezultati ažurirani!");
};

// INIT
document.addEventListener("DOMContentLoaded", () => {
  selectRound(1);

  const vol = document.getElementById('vol');
  if (vol) {
    vol.oninput = function () {
      const a = document.getElementById('audioPlayer');
      if (a) a.volume = this.value;
    };
  }

  socket.emit('admin_get_players');
});

// Switch active quiz (call backend and reload)
async function adminSwitchQuiz(id) {
  if (!confirm('Promijeniti aktivni kviz?')) return;
  try {
    const res = await fetch('/admin/switch_quiz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      location.reload();
    } else {
      alert('Greška: ' + (data.msg || 'Neuspjeh'));
    }
  } catch (e) {
    console.error(e);
    alert('Greška u komunikaciji sa serverom.');
  }
}