const socket = io();

// --- GLOBALNE VARIJABLE ---
let currentRound = 1;
let registrationsOpen = false;
let audioStopTimer = null;
let isQuizStarted = false;
let isPaused = false;
let currentQuestionId = null;
let nextRoundReady = false;
let isLiveArmed = false;
const completedByRound = {};
let roundSongs = [];

// INIT
window.LIVE = window.LIVE || {};

document.addEventListener("DOMContentLoaded", () => {
    selectRound(1);
    loadRoundSongs();
    renderRoundSongs();
    socket.emit('admin_get_players');

    const liveArmToggle = document.getElementById('liveArmToggle');
    if (liveArmToggle) {
        liveArmToggle.addEventListener('change', () => {
            setLiveArmed(liveArmToggle.checked);
        });
    }
    setLiveArmed(false);

    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
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
    if (!isLiveArmed) {
        alert('Live control nije aktiviran. Ukljuci prekidac prije pokretanja.');
        return;
    }
    const audio = document.getElementById('audioPlayer');
    if (nextRoundReady) {
        const nextRound = currentRound + 1;
        if (nextRound > 5) {
            alert("Nema sljedece runde.");
            return;
        }
        if (isPaused) {
            socket.emit('admin_toggle_pause', { paused: false });
            isPaused = false;
        }
        nextRoundReady = false;
        setAutoplayButtonState('start');
        selectRound(nextRound);
        startFirstTime();
        return;
    }
    if (!isQuizStarted) {
        startFirstTime();
        return;
    }
    // Pošalji novu vrijednost na server, ne ažuriraj lokalno prvo
    const newPauseState = !isPaused;
    socket.emit('admin_toggle_pause', { paused: newPauseState });
}

function setLiveArmed(armed) {
    isLiveArmed = !!armed;
    const liveArmToggle = document.getElementById('liveArmToggle');
    if (liveArmToggle) liveArmToggle.checked = isLiveArmed;

    const liveArmLabel = document.getElementById('liveArmLabel');
    if (liveArmLabel) {
        liveArmLabel.textContent = isLiveArmed ? 'LIVE CONTROL: ON' : 'LIVE CONTROL: OFF';
        liveArmLabel.classList.toggle('text-warning', !isLiveArmed);
        liveArmLabel.classList.toggle('text-success', isLiveArmed);
    }

    const btn = document.getElementById('btn-autoplay');
    if (btn) btn.disabled = !isLiveArmed;

    socket.emit('admin_live_arm', { armed: isLiveArmed });
}

function updateControlUI(isPaused) {
    if (nextRoundReady) return;
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

function setAutoplayButtonState(state, roundNum = null) {
    const btnText = document.getElementById('control-text');
    const btnIcon = document.getElementById('control-icon');
    const btn = document.getElementById('btn-autoplay');
    if (!btnText || !btnIcon || !btn) return;

    if (state === 'next-round') {
        const label = roundNum ? `SLJEDECA RUNDA (R${roundNum})` : 'SLJEDECA RUNDA';
        btnText.innerText = label;
        btnIcon.className = "bi bi-fast-forward-fill me-2";
        btn.className = "btn btn-lg btn-warning w-100";
        return;
    }

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
                <button class="btn btn-xs btn-outline-warning me-1" onclick="LIVE.lockPlayer('${p.name}')" title="Lock"><i class="bi bi-slash-circle"></i></button>
                <button class="btn btn-xs btn-outline-danger" onclick="deletePlayer('${p.name}')" title="Obriši"><i class="bi bi-trash"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
        updateStatusDot(document.getElementById(`status-dot-${p.name}`), p.status);
    });
}

// Store data globally for filtering
let gradingData = [];

function renderGradingTableServerShape(data) {
    gradingData = data || []; // Store for filtering
    const tbody = document.getElementById('gradingBody');
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-muted">Čekam prve odgovore...</td></tr>';
        return;
    }

    // Sortiranje: prvo po rundi, pa po poziciji, pa po imenu igrača
    data.sort((a, b) => {
        if (a.round_number !== b.round_number) return a.round_number - b.round_number;
        if (a.position !== b.position) return a.position - b.position;
        return a.player_name.localeCompare(b.player_name);
    });

    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.className = 'align-middle border-bottom border-secondary grading-row';
        tr.dataset.tim = row.player_name.toLowerCase();
        tr.dataset.runda = row.round_number || '';
        tr.dataset.pozicija = row.position || '';
        tr.dataset.izvodjac = (row.artist_guess || '').toLowerCase();
        tr.dataset.naslov = (row.title_guess || '').toLowerCase();
        tr.dataset.dodatno = (row.extra_guess || '').toLowerCase();
        const extraApplicable = row.question_type === 'simultaneous';
        tr.innerHTML = `
            <td class="ps-3">
                <div class="fw-bold text-info">${row.player_name}</div>
                <small class="text-secondary">ID: ${row.question_id}</small>
            </td>
            <td class="text-center">
                <span class="badge bg-warning text-dark">${row.round_number || '-'}</span>
            </td>
            <td class="text-center">
                <span class="badge bg-info text-dark">${row.position || '-'}</span>
            </td>
            <td>
                <div class="text-white small mb-1">Izvođač: <strong>${row.artist_guess || '-'}</strong></div>
                ${generateScoreBtns(row.id, 'artist', row.artist_points)}
            </td>
            <td>
                <div class="text-white small mb-1">Naslov: <strong>${row.title_guess || '-'}</strong></div>
                ${generateScoreBtns(row.id, 'title', row.title_points)}
            </td>
            <td>
                <div class="text-white small mb-1">Dodatno: <strong>${row.extra_guess || '-'}</strong></div>
                ${generateScoreBtns(row.id, 'extra', row.extra_points, !extraApplicable)}
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
    else if (status === 'locked') el.classList.add('bg-warning');
    else el.classList.add('bg-secondary');
}

function generateScoreBtns(id, type, currentScore, disabled = false) {
    const scores = [0, 0.5, 1];
    const labels = ['0', '½', '1'];
    const colors = ['danger', 'warning', 'success'];
    const disabledAttr = disabled ? 'disabled aria-disabled="true"' : '';
    
    let html = '<div class="btn-group btn-group-sm score-group">';
    scores.forEach((val, i) => {
        const active = currentScore === val ? 'active' : '';
        html += `<button type="button" class="btn btn-outline-${colors[i]} ${active}" ${disabledAttr}
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
    currentQuestionId = null;
    if (!completedByRound[currentRound]) {
        completedByRound[currentRound] = new Set();
    }
    if (!nextRoundReady) {
        setAutoplayButtonState('start');
        isQuizStarted = false;
    }
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
    renderRoundSongs();
    // Automatski povuci podatke za tu rundu u grading tablicu
    socket.emit('admin_request_grading', { round: currentRound });
}

function loadRoundSongs() {
    const rows = document.querySelectorAll('.song-row');
    roundSongs = Array.from(rows).map(row => ({
        id: parseInt(row.dataset.id, 10),
        round: parseInt(row.dataset.round, 10),
        position: parseInt(row.dataset.position || '0', 10),
        artist: row.dataset.artist || '',
        title: row.dataset.title || ''
    }));
}

function renderRoundSongs() {
    const tbody = document.getElementById('roundSongsBody');
    const count = document.getElementById('roundSongCount');
    if (!tbody) return;

    const songs = roundSongs
        .filter(s => s.round === currentRound)
        .sort((a, b) => a.position - b.position);

    if (count) count.textContent = songs.length;
    tbody.innerHTML = '';

    if (!songs.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="p-3 text-center text-muted">Nema pitanja u ovoj rundi.</td></tr>';
        return;
    }

    const completed = completedByRound[currentRound] || new Set();

    songs.forEach(song => {
        let statusLabel = 'CEKA';
        let badgeClass = 'bg-secondary';
        if (song.id === currentQuestionId) {
            statusLabel = 'ONLINE';
            badgeClass = 'bg-danger';
        } else if (completed.has(song.id)) {
            statusLabel = 'PROSLO';
            badgeClass = 'bg-success';
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="ps-3 text-warning fw-bold">${song.position || '-'}</td>
            <td>
                <div class="text-white text-truncate" style="max-width: 180px;">${song.artist}</div>
                <div class="small text-muted text-truncate" style="max-width: 180px;">${song.title}</div>
            </td>
            <td class="text-end pe-3">
                <span class="badge ${badgeClass} status-badge">${statusLabel}</span>
            </td>
        `;
        tbody.appendChild(tr);
    });
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
    if (!completedByRound[currentRound]) {
        completedByRound[currentRound] = new Set();
    }
    currentQuestionId = data.id;
    nextRoundReady = false;
    renderRoundSongs();
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
    const indexLabel = data.question_index || data.id || '';
    const counterStr = data.total_questions ? `${indexLabel} / ${data.total_questions}` : `${indexLabel}.`;
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

socket.on('round_locked', (data) => {
    if (!currentQuestionId) return;
    if (!completedByRound[currentRound]) {
        completedByRound[currentRound] = new Set();
    }
    completedByRound[currentRound].add(currentQuestionId);
    renderRoundSongs();
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

socket.on('admin_round_finished', (data) => {
    const finishedRound = data.round || currentRound;
    if (!completedByRound[finishedRound]) {
        completedByRound[finishedRound] = new Set();
    }
    roundSongs
        .filter(s => s.round === finishedRound)
        .forEach(s => completedByRound[finishedRound].add(s.id));
    currentQuestionId = null;
    isQuizStarted = false;
    nextRoundReady = true;
    renderRoundSongs();
    const nextRound = finishedRound + 1;
    if (nextRound <= 5) {
        setAutoplayButtonState('next-round', nextRound);
    } else {
        setAutoplayButtonState('start');
    }
});

socket.on('admin_live_guard_blocked', (data) => {
    alert(data?.message || 'Live control nije aktiviran.');
});


// --- LIVE FUNKCIJE ZA KONTROLU OCJENJIVANJA ---

LIVE.setScore = async function(btnEl, answerId, type, points) {
    try {
        const res = await fetch('/api/update_score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                answer_id: answerId,
                type: type,
                value: points
            })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            // Ažuriraj UI - označi aktivni gumb
            const group = btnEl.parentElement;
            group.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            btnEl.classList.add('active');
        }
    } catch (err) {
        console.error('Greška pri ažuriranju bodova:', err);
    }
};

LIVE.lockPlayer = function(playerName) {
    if (confirm(`Zaključati igrača "${playerName}" za ostatak kviza?`)) {
        socket.emit('admin_lock_player', { player_name: playerName });
    }
};

LIVE.filterTable = function() {
    const filterTim = document.getElementById('filterTim').value.toLowerCase();
    const filterRunda = document.getElementById('filterRunda').value.toLowerCase();
    const filterPozicija = document.getElementById('filterPozicija').value.toLowerCase();
    const filterIzvodjac = document.getElementById('filterIzvodjac').value.toLowerCase();
    const filterNaslov = document.getElementById('filterNaslov').value.toLowerCase();
    const filterDodatno = document.getElementById('filterDodatno').value.toLowerCase();

    const rows = document.querySelectorAll('.grading-row');
    rows.forEach(row => {
        const tim = row.dataset.tim || '';
        const runda = row.dataset.runda || '';
        const pozicija = row.dataset.pozicija || '';
        const izvodjac = row.dataset.izvodjac || '';
        const naslov = row.dataset.naslov || '';
        const dodatno = row.dataset.dodatno || '';

        const matchTim = tim.includes(filterTim);
        const matchRunda = runda.includes(filterRunda);
        const matchPozicija = pozicija.includes(filterPozicija);
        const matchIzvodjac = izvodjac.includes(filterIzvodjac);
        const matchNaslov = naslov.includes(filterNaslov);
        const matchDodatno = dodatno.includes(filterDodatno);

        if (matchTim && matchRunda && matchPozicija && matchIzvodjac && matchNaslov && matchDodatno) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
};