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
});