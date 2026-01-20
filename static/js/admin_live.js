/* static/js/admin_live.js - FINAL VERSION */

const socket = io();

// --- GLOBALNE VARIJABLE ---
let currentRound = 1;
let autoPlayActive = false;
let playQueue = [];
let currentQueueIndex = 0;
let autoplayTimeout = null;

// --- SOCKET LISTENERS ---

// 1. KLJUČNO: Slušaj kad server pošalje audio datoteku (OVO JE FALILO)
socket.on('play_audio', (data) => {
    const audio = document.getElementById('audioPlayer');
    if (audio) {
        // Timestamp sprječava cacheiranje stare pjesme
        audio.src = '/snippets/' + data.file + '?t=' + new Date().getTime();
        
        const vol = document.getElementById('vol');
        if (vol) audio.volume = vol.value;
        
        audio.play().catch(error => {
            console.error("Autoplay blokiran:", error);
        });
    }
});

// 2. Prikaz ocjenjivanja
socket.on('admin_grading_data', (data) => {
    document.getElementById('playlist-card').style.display = 'none';
    document.getElementById('grading-view').style.display = 'block';
    renderGradingTable(data);
});

// 3. Status igrača
socket.on('admin_player_status_change', (d) => {
    console.log(`Player ${d.name} is ${d.status}`);
});

// --- FUNKCIJE ZA UPRAVLJANJE RUNDAMA ---

function selectRound(r) {
    currentRound = r;
    console.log("Selecting Round:", r);

    // 1. Ažuriraj gumbe
    document.querySelectorAll('.round-tab').forEach((btn, i) => {
        if (i + 1 == r) {
            btn.classList.add('active', 'btn-danger');
            btn.classList.remove('btn-outline-light');
        } else {
            btn.classList.remove('active', 'btn-danger');
            btn.classList.add('btn-outline-light');
        }
    });

    // 2. Filtriraj tablicu
    const rows = document.querySelectorAll('.song-row');
    let found = 0;

    rows.forEach(row => {
        const rowRound = row.getAttribute('data-round');
        if (rowRound == r) {
            row.style.display = 'table-row';
            row.classList.remove('hidden-round');
            found++;
        } else {
            row.style.display = 'none';
            row.classList.add('hidden-round');
        }
    });
    
    // Javi serveru
    socket.emit('admin_change_round', {round: r});
}

// --- AUDIO PLAYER LOGIKA ---

function playSong(id) {
    // Resetiraj vizualni stil
    document.querySelectorAll('.song-row').forEach(row => {
        row.classList.remove('table-active', 'border-warning', 'border-3');
        row.style.opacity = "1";
    });

    // Označi red
    const row = document.getElementById('row-' + id);
    if (row) {
        row.classList.add('table-active', 'border-warning', 'border-3');
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        const artist = row.getAttribute('data-artist');
        const title = row.getAttribute('data-title');
        const djElem = document.getElementById('dj-console');
        if(djElem) {
            djElem.style.display = 'block';
            document.getElementById('np-artist').innerText = artist;
            document.getElementById('np-title').innerText = title;
        }
    }

    // Pošalji zahtjev
    socket.emit('admin_play_song', {id: parseInt(id)});
}

function stopMusic() {
    clearTimeout(autoplayTimeout);
    autoPlayActive = false;
    
    const btn = document.getElementById('btn-autoplay');
    if(btn) {
        btn.classList.replace('btn-danger', 'btn-outline-danger');
        btn.innerHTML = '<i class="bi bi-collection-play"></i> AUTOPLAY';
    }

    const audio = document.getElementById('audioPlayer');
    if(audio) audio.pause();
}

// --- AUTOPLAY LOGIKA ---

function toggleAutoplay() {
    // TRIK ZA BROWSER: Odmah aktiviraj audio context
    const audio = document.getElementById('audioPlayer');
    if(audio) {
        audio.play().catch(() => {}); 
        audio.pause();
    }
    
    autoPlayActive = !autoPlayActive;
    const btn = document.getElementById('btn-autoplay');
    
    if (autoPlayActive) {
        btn.classList.replace('btn-outline-danger', 'btn-danger');
        btn.innerHTML = '<i class="bi bi-stop-circle-fill"></i> STOP AUTOPLAY';
        
        playQueue = [];
        const visibleRows = document.querySelectorAll('.song-row:not(.hidden-round)');
        
        if(visibleRows.length === 0) {
            alert("Nema pjesama u ovoj rundi!");
            toggleAutoplay();
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
        alert("Kraj runde! Pokrećem timer...");
        startTimer();
        return;
    }

    const songId = playQueue[currentQueueIndex];
    const row = document.getElementById('row-' + songId);
    
    let duration = 15;
    if (row && row.getAttribute('data-duration')) {
        const d = parseFloat(row.getAttribute('data-duration'));
        if(!isNaN(d) && d > 0) duration = d;
    }

    playSong(songId);
    currentQueueIndex++;

    const waitTime = (duration * 1000) + 5000;
    
    clearTimeout(autoplayTimeout);
    autoplayTimeout = setTimeout(() => {
        if(autoPlayActive) {
            playNextInQueue();
        }
    }, waitTime);
}

// --- TIMER I GRADING ---

function startTimer() {
    socket.emit('admin_start_timer', {sec: 60});
    
    let sec = 60;
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
            if(confirm("Vrijeme je isteklo! Zaključati rundu?")) {
                socket.emit('admin_lock_round', {round: currentRound});
            }
        }
    }, 1000);
}

function renderGradingTable(data) {
    const tb = document.getElementById('gradingBody');
    tb.innerHTML = "";
    data.forEach(d => {
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
});