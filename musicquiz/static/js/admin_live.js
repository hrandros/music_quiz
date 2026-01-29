const socket = io();

// --- GLOBALNE VARIJABLE ---
let currentRound = 1;
let registrationsOpen = false;
let audioStopTimer = null;
let isQuizStarted = false;
let isPaused = false;

// INIT
window.LIVE = window.LIVE || {};

document.addEventListener("DOMContentLoaded", () => {
    selectRound(1);
    socket.emit('admin_get_players');
});


// --- FUNKCIJE ZA KONTROLU (GUMBI) ---

function unlockRegistrations() {
    const btn = document.getElementById('reg-toggle-btn');
    if (!btn) return;

    socket.emit('admin_toggle_registrations', { open: true });

    btn.disabled = true;
    btn.classList.replace('btn-info', 'btn-secondary');
    btn.innerHTML = '<i class="bi bi-check-all me-2"></i>PRIJAVE SU OTVORENE';
}

// 2. Modifikacija startFirstTime da NE dira prijave
function startFirstTime() {
    const firstRow = document.querySelector('.song-row:not(.hidden-round)');
    if (!firstRow) {
        alert("Nema pjesama u ovoj rundi!");
        return;
    }

    const firstSongId = firstRow.id.replace('row-', '');
    
    if (confirm("Pokrenuti automatski niz pjesama za ovu rundu?")) {
        isQuizStarted = true;
        socket.emit('admin_start_auto_run', { 
            id: parseInt(firstSongId, 10), 
            round: currentRound 
        });
        updateControlUI(false);
    }
}

function handleQuizControl() {
    const audio = document.getElementById('audioPlayer');
    if (!isQuizStarted) {
        startFirstTime();
        return;
    }
    isPaused = !isPaused;
    socket.emit('admin_toggle_pause', { paused: isPaused });
}

function updateControlUI(isPaused) {
    const btnText = document.getElementById('control-text');
    const btnIcon = document.getElementById('control-icon');
    const btn = document.getElementById('btn-autoplay');

    if (isPaused) {
        btnText.innerText = "NASTAVI";
        btnIcon.className = "bi bi-play-fill me-2";
        btn.classList.replace('btn-outline-danger', 'btn-success');
    } else {
        btnText.innerText = "PAUZIRAJ";
        btnIcon.className = "bi bi-pause-circle-fill me-2";
        btn.classList.replace('btn-success', 'btn-outline-danger');
        btn.classList.replace('btn-outline-danger', 'btn-danger');
    }
}

function stopMusic() {
    if (audioStopTimer) clearTimeout(audioStopTimer);
    const audio = document.getElementById('audioPlayer');
    if (audio) {
        audio.pause();
        audio.currentTime = 0;
    }
    isQuizStarted = false;
    const btnText = document.getElementById('control-text');
    const btnIcon = document.getElementById('control-icon');
    const btn = document.getElementById('btn-autoplay');
    
    btnText.innerText = "KRENI KVIZ";
    btnIcon.className = "bi bi-play-circle-fill me-2";
    btn.className = "btn btn-lg btn-outline-danger w-100";
}

// --- RENDER FUNKCIJE ---

function renderPlayerList(players) {
    const tbody = document.getElementById('playerListBody');
    const countBadge = document.getElementById('playerCount');
    if (!tbody) return;
    if (countBadge) countBadge.innerText = players.length;

    tbody.innerHTML = "";
    players.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="width:20px;"><span id="status-dot-${p.name}" class="d-inline-block rounded-circle" style="width:10px; height:10px;"></span></td>
            <td class="text-white fw-bold text-truncate" style="max-width:150px;">
                ${p.name}<div class="text-muted" style="font-size:0.7em;">${p.score} bodova</div>
            </td>
            <td class="text-end">
                <button class="btn btn-xs btn-outline-warning me-1" onclick="lockPlayer('${p.name}')" title="Lock"><i class="bi bi-slash-circle"></i></button>
                <button class="btn btn-xs btn-outline-danger" onclick="deletePlayer('${p.name}')" title="Obriši"><i class="bi bi-trash"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
        updateStatusDot(document.getElementById(`status-dot-${p.name}`), p.status);
    });
}

function renderGradingTableServerShape(data) {
    const tbody = document.getElementById('gradingBody'); // Provjeri imaš li ovaj ID u HTML-u
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="p-4 text-center text-muted">Čekam prve odgovore...</td></tr>';
        return;
    }

    // Sortiranje: prvo po pjesmi, pa po imenu igrača
    data.sort((a, b) => {
        if (a.song_id !== b.song_id) return a.song_id - b.song_id;
        return a.player_name.localeCompare(b.player_name);
    });

    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.className = 'align-middle border-bottom border-secondary';
        tr.innerHTML = `
            <td class="ps-3">
                <div class="fw-bold text-info">${row.player_name}</div>
                <small class="text-secondary">Pjesma ID: ${row.song_id}</small>
            </td>
            <td>
                <div class="text-white small mb-1">Izvođač: <strong>${row.artist_guess || '-'}</strong></div>
                ${generateScoreBtns(row.id, 'artist', row.artist_points)}
            </td>
            <td>
                <div class="text-white small mb-1">Naslov: <strong>${row.title_guess || '-'}</strong></div>
                ${generateScoreBtns(row.id, 'title', row.title_points)}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// --- POMOĆNE FUNKCIJE ---

function updateStatusDot(el, status) {
    if (!el) return;
    el.className = "d-inline-block rounded-circle";
    if (status === 'active') el.classList.add('bg-success');
    else if (status === 'away') el.classList.add('bg-danger', 'animate__animated', 'animate__flash', 'animate__infinite');
    else el.classList.add('bg-secondary');
}

function generateScoreBtns(id, type, currentScore) {
    const scores = [0, 0.5, 1];
    const labels = ['0', '½', '1'];
    const colors = ['danger', 'warning', 'success'];
    
    let html = '<div class="btn-group btn-group-sm score-group">';
    scores.forEach((val, i) => {
        const active = currentScore === val ? 'active' : '';
        html += `<button type="button" class="btn btn-outline-${colors[i]} ${active}" 
                 onclick="LIVE.setScore(this, ${id}, '${type}', ${val})">${labels[i]}</button>`;
    });
    html += '</div>';
    return html;
}


function deletePlayer(name) {
    if (confirm(`Trajno obrisati tim "${name}" i sve njihove odgovore?`)) {
        socket.emit('admin_delete_player', { player_name: name });
    }
}

function selectRound(r) {
    currentRound = parseInt(r, 10);
    document.querySelectorAll('.round-tab').forEach((btn, i) => {
        btn.classList.toggle('active', i + 1 === currentRound);
        btn.classList.toggle('btn-danger', i + 1 === currentRound);
        btn.classList.toggle('btn-outline-light', i + 1 !== currentRound);
    });

    document.querySelectorAll('.song-row').forEach(row => {
        const rr = parseInt(row.getAttribute('data-round'), 10);
        const isMatch = rr === currentRound;
        row.style.display = isMatch ? 'table-row' : 'none';
        row.classList.toggle('hidden-round', !isMatch);
    });
    
    document.getElementById('gradingRoundNum').innerText = currentRound;
    // Automatski povuci podatke za tu rundu u grading tablicu
    socket.emit('admin_request_grading', { round: currentRound });
}

function setVol(val) {
    const audio = document.getElementById('audioPlayer');
    if (audio) audio.volume = val;
}

async function adminSwitchQuiz(id) {
    if (!confirm('Promijeniti aktivni kviz?')) return;
    const res = await fetch('/admin/switch_quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'ok') location.reload();
}

// --- SOCKET LISTENERS ---
socket.on('play_audio', (data) => {
    document.querySelectorAll('.song-row').forEach(row => {
        row.classList.remove('table-active', 'border-warning', 'border-3');
    });
    const row = document.getElementById('row-' + data.id);
    if (row) {
        row.classList.add('table-active', 'border-warning', 'border-3');
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    const djConsole = document.getElementById('dj-console');
    if (djConsole) { djConsole.style.display = 'block'; }
    const counterStr = data.total_songs ? `${data.song_index} / ${data.total_songs}` : `${data.song_index}.`;
    ['np-artist', 'np-artist-mini'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = `<span class="text-danger">${counterStr}</span> | ${data.artist || 'Nepoznato'}`;
    });
    ['np-title', 'np-title-mini'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = data.title || '---';
    });
    const audio = document.getElementById('audioPlayer');
    if (!audio) return;
    if (typeof audioStopTimer !== 'undefined' && audioStopTimer) {
        clearTimeout(audioStopTimer);
    }
    audio.onloadedmetadata = function () {
        audio.currentTime = data.start || 0;
        const volInput = document.getElementById('vol');
        if (volInput) audio.volume = volInput.value;
        audio.play().then(() => {
            audioStopTimer = setTimeout(() => {
                audio.pause();
                console.log("Audio automatski zaustavljen.");
            }, (data.duration || 30) * 1000);
        }).catch(err => {
            console.warn("Autoplay blokiran. Klikni bilo gdje na stranicu pa probaj opet.", err);
        });
    };
    audio.src = data.url;
    isQuizStarted = true;
    updateControlUI(false);
});

// Slušaj promjenu stanja sa servera (sinkronizacija)
socket.on('quiz_pause_state', (data) => {
    isPaused = data.paused;
    const audio = document.getElementById('audioPlayer');
    
    if (isPaused) {
        audio.pause();
        updateControlUI(true); // Zeleni gumb "NASTAVI"
    } else {
        audio.play();
        updateControlUI(false); // Crveni gumb "PAUZIRAJ"
    }
});

// Liste igrača
socket.on('admin_player_list_full', (players) => renderPlayerList(players));
socket.on('admin_update_player_list', (players) => renderPlayerList(players));
socket.on('admin_single_player_update', (d) => {
    const dot = document.getElementById(`status-dot-${d.name}`);
    if (dot) updateStatusDot(dot, d.status);
});

// Podaci za ocjenjivanje (Grading)
socket.on('admin_receive_grading_data', (data) => {
    renderGradingTableServerShape(data);
});


// LIVE FUNKCIJE ZA KONTROLU OCJENJIVANJA

function deletePlayer(name) {
    if (confirm(`Trajno obrisati tim "${name}" i sve njihove odgovore?`)) {
        socket.emit('admin_delete_player', { player_name: name });
    }
}

function selectRound(r) {
    currentRound = parseInt(r, 10);
    document.querySelectorAll('.round-tab').forEach((btn, i) => {
        btn.classList.toggle('active', i + 1 === currentRound);
        btn.classList.toggle('btn-danger', i + 1 === currentRound);
        btn.classList.toggle('btn-outline-light', i + 1 !== currentRound);
    });

    document.querySelectorAll('.song-row').forEach(row => {
        const rr = parseInt(row.getAttribute('data-round'), 10);
        const isMatch = rr === currentRound;
        row.style.display = isMatch ? 'table-row' : 'none';
        row.classList.toggle('hidden-round', !isMatch);
    });
    
    document.getElementById('gradingRoundNum').innerText = currentRound;
    // Automatski povuci podatke za tu rundu u grading tablicu
    socket.emit('admin_request_grading', { round: currentRound });
}

function setVol(val) {
    const audio = document.getElementById('audioPlayer');
    if (audio) audio.volume = val;
}

// INIT
document.addEventListener("DOMContentLoaded", () => {
    selectRound(1);
    socket.emit('admin_get_players');
});

async function adminSwitchQuiz(id) {
    if (!confirm('Promijeniti aktivni kviz?')) return;
    const res = await fetch('/admin/switch_quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'ok') location.reload();
}