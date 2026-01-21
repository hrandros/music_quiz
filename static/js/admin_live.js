const socket = io();

// --- GLOBALNE VARIJABLE ---
let currentRound = 1;
let autoPlayActive = false;
let playQueue = [];
let currentQueueIndex = 0;
let autoplayTimeout = null;   // Timer za sljedeću pjesmu u redu
let audioStopTimer = null;    // Timer za zaustavljanje trenutne pjesme (NOVO)

// --- SOCKET LISTENERS ---
socket.on('play_audio', (data) => {
    // data = { url: "...", start: 45.0, duration: 15.0 }
    const audio = document.getElementById('audioPlayer');
    
    // Resetiraj timer za gašenje ako svira prethodna
    if (audioStopTimer) clearTimeout(audioStopTimer);

    if (audio) {
        audio.src = data.url; // Učitaj cijelu pjesmu
        
        // Čekamo da browser učita podatke o trajanju da možemo skočiti
        audio.onloadedmetadata = function() {
            audio.currentTime = data.start; // Skoči na početak isječka
            
            const vol = document.getElementById('vol');
            if (vol) audio.volume = vol.value;
            
            audio.play().then(() => {
                // Postavi timer da stane nakon 'duration' sekundi
                audioStopTimer = setTimeout(() => {
                    audio.pause();
                }, data.duration * 1000);
            }).catch(error => {
                console.error("Greška pri reprodukciji:", error);
            });
        };
    }
});

socket.on('admin_grading_data', (data) => {
    document.getElementById('playlist-card').style.display = 'none';
    document.getElementById('grading-view').style.display = 'block';
    renderGradingTable(data);
});

socket.on('admin_player_status_change', (d) => {
    console.log(`Player ${d.name} is ${d.status}`);
});

// Primanje pune liste (kod refresha)
socket.on('admin_player_list_full', (players) => {
    renderPlayerList(players);
});

// Ažuriranje liste (kad se netko novi spoji)
socket.on('admin_update_player_list', (players) => {
    renderPlayerList(players);
});

// Ažuriranje statusa pojedinca (Anti-Cheat realtime)
socket.on('admin_single_player_update', (d) => {
    const statusDot = document.getElementById(`status-dot-${d.name}`);
    if(statusDot) {
        updateStatusDot(statusDot, d.status);
    }
});

// Potvrda da je igrač zaključan
socket.on('admin_lock_confirmed', (d) => {
    const btn = document.getElementById(`btn-lock-${d.player}`);
    if(btn) {
        btn.classList.remove('btn-outline-danger');
        btn.classList.add('btn-danger');
        btn.innerHTML = '<i class="bi bi-lock-fill"></i>';
        btn.disabled = true;
    }
});

function renderPlayerList(players) {
    const tbody = document.getElementById('playerListBody');
    const countBadge = document.getElementById('playerCount');
    if(!tbody) return;

    countBadge.innerText = players.length;
    tbody.innerHTML = "";

    players.forEach(p => {
        let statusColor = 'bg-secondary'; // offline
        if(p.status === 'active') statusColor = 'bg-success'; // u aplikaciji
        if(p.status === 'away') statusColor = 'bg-danger animate__animated animate__flash animate__infinite'; // izašao van (google?)

        tbody.innerHTML += `
        <tr>
            <td style="width: 20px;">
                <span id="status-dot-${p.name}" class="d-inline-block rounded-circle ${statusColor}" style="width:10px; height:10px;" title="${p.status}"></span>
            </td>
            <td class="text-white fw-bold text-truncate" style="max-width: 150px;">
                ${p.name}
                <div class="text-muted" style="font-size: 0.7em;">${p.score} bodova</div>
            </td>
            <td class="text-end">
                <button id="btn-lock-${p.name}" class="btn btn-xs btn-outline-danger" 
                        title="Zabrani odgovaranje za ovu pjesmu"
                        onclick="lockPlayer('${p.name}')">
                    <i class="bi bi-slash-circle"></i>
                </button>
            </td>
        </tr>`;
    });
}

function updateStatusDot(el, status) {
    el.className = "d-inline-block rounded-circle"; // Reset
    if(status === 'active') el.classList.add('bg-success');
    else if(status === 'away') el.classList.add('bg-danger', 'animate__animated', 'animate__flash', 'animate__infinite');
    else el.classList.add('bg-secondary');
}

function lockPlayer(name) {
    // Trenutno svirana pjesma (moraš imati globalnu varijablu currentSongId iz admin_play_song dijela)
    // Ako nemaš globalnu varijablu, možeš je dohvatiti iz DOM-a aktivnog reda
    const activeRow = document.querySelector('.song-row.table-active');
    if(!activeRow) {
        alert("Nijedna pjesma ne svira trenutno.");
        return;
    }
    const songId = activeRow.getAttribute('data-id');

    if(confirm(`Zabraniti unos timu "${name}" za ovu pjesmu?`)) {
        socket.emit('admin_lock_single_player', {
            player_name: name,
            song_id: songId
        });
    }
}

// --- FUNKCIJE ZA UPRAVLJANJE RUNDAMA ---
function selectRound(r) {
    currentRound = r;
    console.log("Selecting Round:", r);
    document.querySelectorAll('.round-tab').forEach((btn, i) => {
        if (i + 1 == r) {
            btn.classList.add('active', 'btn-danger');
            btn.classList.remove('btn-outline-light');
        } else {
            btn.classList.remove('active', 'btn-danger');
            btn.classList.add('btn-outline-light');
        }
    });
    const rows = document.querySelectorAll('.song-row');
    rows.forEach(row => {
        const rowRound = row.getAttribute('data-round');
        if (rowRound == r) {
            row.style.display = 'table-row';
            row.classList.remove('hidden-round');
        } else {
            row.style.display = 'none';
            row.classList.add('hidden-round');
        }
    });
    socket.emit('admin_change_round', {round: r});
}

// --- AUDIO PLAYER LOGIKA ---
function playSong(id) {
    // UI Update (highlight reda)
    document.querySelectorAll('.song-row').forEach(row => {
        row.classList.remove('table-active', 'border-warning', 'border-3');
        row.style.opacity = "1";
    });
    const row = document.getElementById('row-' + id);
    if (row) {
        row.classList.add('table-active', 'border-warning', 'border-3');
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Ažuriraj "Currently Playing" na ekranu admina
        const artist = row.getAttribute('data-artist');
        const title = row.getAttribute('data-title');
        const djElem = document.getElementById('dj-console');
        if(djElem) {
            djElem.style.display = 'block';
            document.getElementById('np-artist').innerText = artist;
            document.getElementById('np-title').innerText = title;
        }
    }
    // Šaljemo zahtjev serveru -> server vraća 'play_audio' event
    socket.emit('admin_play_song', {id: parseInt(id)});
}

function stopMusic() {
    // Očisti sve timere
    if (autoplayTimeout) clearTimeout(autoplayTimeout);
    if (audioStopTimer) clearTimeout(audioStopTimer);

    autoPlayActive = false;
    
    // UI update gumba
    const btn = document.getElementById('btn-autoplay');
    if(btn) {
        btn.classList.replace('btn-danger', 'btn-outline-danger');
        btn.innerHTML = '<i class="bi bi-collection-play"></i> AUTOPLAY';
    }
    
    // Stvarna pauza audio playera
    const audio = document.getElementById('audioPlayer');
    if(audio) audio.pause();
}

// --- AUTOPLAY LOGIKA ---
function toggleAutoplay() {
    autoPlayActive = !autoPlayActive;
    const btn = document.getElementById('btn-autoplay');
    
    if (autoPlayActive) {
        // Start Autoplay
        btn.classList.replace('btn-outline-danger', 'btn-danger');
        btn.innerHTML = '<i class="bi bi-stop-circle-fill"></i> STOP AUTOPLAY';
        
        playQueue = [];
        const visibleRows = document.querySelectorAll('.song-row:not(.hidden-round)');
        
        if(visibleRows.length === 0) {
            alert("Nema pjesama u ovoj rundi!");
            toggleAutoplay(); // Ugasi odmah
            return;
        }
        
        visibleRows.forEach(row => {
            const id = row.id.replace('row-', '');
            playQueue.push(id);
        });
        
        currentQueueIndex = 0;
        playNextInQueue();

    } else {
        // Stop Autoplay
        stopMusic();
    }
}

function playNextInQueue() {
    if (!autoPlayActive) return;
    
    if (currentQueueIndex >= playQueue.length) {
        stopMusic();
        alert("Kraj runde! Pokrećem timer...");
        startTimer();
        return;
    }

    const songId = playQueue[currentQueueIndex];
    const row = document.getElementById('row-' + songId);
    
    // Dohvati trajanje iz HTML atributa (mora se podudarati s bazom)
    let duration = 15;
    if (row && row.getAttribute('data-duration')) {
        const d = parseFloat(row.getAttribute('data-duration'));
        if(!isNaN(d) && d > 0) duration = d;
    }

    playSong(songId); // Ovo pokreće audio
    currentQueueIndex++;

    // Čekaj trajanje pjesme + 5 sekundi pauze prije sljedeće
    const waitTime = (duration * 1000) + 5000;
    
    if (autoplayTimeout) clearTimeout(autoplayTimeout);
    
    autoplayTimeout = setTimeout(() => {
        if(autoPlayActive) {
            playNextInQueue();
        }
    }, waitTime);
}

// --- TIMER I GRADING ---
function startTimer() {
    socket.emit('admin_start_timer', {sec: 30});
    let sec = 30;
    const btn = document.querySelector('button[onclick="startTimer()"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    
    const interval = setInterval(() => {
        sec--;
        btn.innerHTML = `<i class="bi bi-hourglass-split"></i> ${sec}s`;
        if(sec <= 0) {
            clearInterval(interval);
            btn.innerHTML = originalText;
            btn.disabled = false;
            socket.emit('admin_lock_round', {round: currentRound}); 
        }
    }, 1000);
}

function renderGradingTable(data) {
    const tb = document.getElementById('gradingBody');
    tb.innerHTML = "";
    data.forEach(d => {
        // Generiranje HTML-a tablice ocjenjivanja
        tb.innerHTML += `<tr>
            <td class="text-white fw-bold">${d.player}</td>
            <td>
                <div class="small text-muted mb-1">Odg: <span class="text-white">${d.artist_guess || '-'}</span></div>
                <div class="small text-secondary" style="font-size:0.7em">Točno: ${d.c_artist}</div>
                <div class="btn-group btn-group-sm mt-1">
                    <button class="btn ${d.artist_pts==1?'btn-success':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'artist_pts',1)">1</button>
                    <button class="btn ${d.artist_pts==0.5?'btn-warning':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'artist_pts',0.5)">½</button>
                    <button class="btn ${d.artist_pts==0?'btn-danger':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'artist_pts',0)">0</button>
                </div>
            </td>
            <td>
                <div class="small text-muted mb-1">Odg: <span class="text-white">${d.title_guess || '-'}</span></div>
                <div class="small text-secondary" style="font-size:0.7em">Točno: ${d.c_title}</div>
                <div class="btn-group btn-group-sm mt-1">
                    <button class="btn ${d.title_pts==1?'btn-success':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'title_pts',1)">1</button>
                    <button class="btn ${d.title_pts==0.5?'btn-warning':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'title_pts',0.5)">½</button>
                    <button class="btn ${d.title_pts==0?'btn-danger':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'title_pts',0)">0</button>
                </div>
            </td>
        </tr>`;
    });
}

function rate(p, sid, field, val) {
    let payload = {player:p, song_id:sid};
    payload[field] = val;
    socket.emit('admin_grade_answer', payload);
}

// INICIJALIZACIJA
document.addEventListener("DOMContentLoaded", () => {
    selectRound(1);
    const vol = document.getElementById('vol');
    if(vol) {
        vol.oninput = function() {
            const a = document.getElementById('audioPlayer');
            if(a) a.volume = this.value;
        }
    }
    socket.emit('admin_get_players');
});

// --- LOGIKA OCJENJIVANJA ---

LIVE.openGrading = function() {
    // 1. Sakrij playlistu, prikaži loading
    document.getElementById('playlist-card').style.display = 'none';
    const gView = document.getElementById('grading-view');
    gView.style.display = 'block';
    document.getElementById('gradingRoundNum').innerText = currentRound;
    document.getElementById('gradingBody').innerHTML = '<tr><td colspan="4" class="p-4 text-center"><div class="spinner-border text-info"></div> Učitavam odgovore...</td></tr>';

    // 2. Traži podatke od servera
    socket.emit('admin_request_grading', { round: currentRound });
};

LIVE.closeGrading = function() {
    document.getElementById('grading-view').style.display = 'none';
    document.getElementById('playlist-card').style.display = 'block';
};

// Server šalje podatke
socket.on('admin_receive_grading_data', (data) => {
    const tbody = document.getElementById('gradingBody');
    tbody.innerHTML = "";

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-muted">Nema odgovora u ovoj rundi.</td></tr>';
        return;
    }

    // Sortiraj po pjesmi (song_index) pa po imenu tima
    data.sort((a, b) => {
        if (a.song_index !== b.song_index) return a.song_index - b.song_index;
        return a.player.localeCompare(b.player);
    });

    data.forEach(row => {
        // Generiraj gumbe za Artist bodove (0, 0.5, 1)
        const btnArt = generateScoreBtns(row.answer_id, 'artist', row.artist_pts);
        // Generiraj gumbe za Title bodove
        const btnTit = generateScoreBtns(row.answer_id, 'title', row.title_pts);

        const html = `
            <tr class="align-middle">
                <td class="fw-bold text-secondary">#${row.song_index}</td>
                <td class="fw-bold text-info text-start text-truncate" style="max-width:120px;" title="${row.player}">${row.player}</td>
                
                <td class="text-start position-relative">
                    <div class="d-flex justify-content-between mb-1">
                        <span class="text-white text-truncate" style="max-width:200px;" title="${row.artist_guess || '-'}">${row.artist_guess || '<span class="text-muted">-</span>'}</span>
                        ${btnArt}
                    </div>
                    <div class="small text-success border-top border-secondary pt-1">
                        <i class="bi bi-check-circle-fill me-1"></i> ${row.correct_artist}
                    </div>
                </td>

                <td class="text-start position-relative">
                    <div class="d-flex justify-content-between mb-1">
                        <span class="text-white text-truncate" style="max-width:200px;" title="${row.title_guess || '-'}">${row.title_guess || '<span class="text-muted">-</span>'}</span>
                        ${btnTit}
                    </div>
                    <div class="small text-success border-top border-secondary pt-1">
                         <i class="bi bi-check-circle-fill me-1"></i> ${row.correct_title}
                    </div>
                </td>
            </tr>
        `;
        tbody.innerHTML += html;
    });
});

// Helper za generiranje gumba
function generateScoreBtns(id, type, currentScore) {
    // currentScore je float (0.0, 0.5, 1.0)
    const is0 = currentScore === 0 ? 'active' : '';
    const is05 = currentScore === 0.5 ? 'active' : '';
    const is1 = currentScore === 1 ? 'active' : '';

    return `
    <div class="btn-group btn-group-sm score-group" role="group">
        <button type="button" class="btn btn-outline-danger ${is0}" onclick="LIVE.setScore(this, ${id}, '${type}', 0)">0</button>
        <button type="button" class="btn btn-outline-warning ${is05}" onclick="LIVE.setScore(this, ${id}, '${type}', 0.5)">½</button>
        <button type="button" class="btn btn-outline-success ${is1}" onclick="LIVE.setScore(this, ${id}, '${type}', 1)">1</button>
    </div>
    `;
}

LIVE.setScore = function(btn, ansId, type, val) {
    // Vizualni update odmah (da ne čekamo server)
    const group = btn.parentElement;
    group.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Šalji serveru
    socket.emit('admin_update_score', {
        answer_id: ansId,
        type: type,
        value: val
    });
};

LIVE.finalizeRound = function() {
    if(!confirm("Jeste li sigurni da želite zaključiti ocjenjivanje?\nOvo će ažurirati tablicu poretka na TV-u.")) return;
    
    socket.emit('admin_finalize_round', { round: currentRound });
    
    // Zatvori grading view
    LIVE.closeGrading();
    alert("Rezultati ažurirani!");
};