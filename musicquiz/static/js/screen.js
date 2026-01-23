const socket = io();
const sfx = {
    correct: new Audio('/static/sfx/correct.mp3'),
    lock: new Audio('/static/sfx/lock.mp3')
};

// --- LISTENERS ---

// 1. Ažuriranje statusa (Nova pjesma)
socket.on('screen_update_status', (data) => {
    // Reset prikaza (sakrij odgovore i timer, pokaži glavni info)
    document.getElementById('ansKey').classList.add('d-none');
    document.getElementById('timerOverlay').classList.add('d-none');
    
    // Pokaži elemente za pjesmu
    const visContainer = document.getElementById('visualizer');
    if(visContainer) visContainer.classList.remove('d-none');
    document.getElementById('songDisplay').classList.remove('d-none');

    // Ažuriraj broj runde
    const rDisplay = document.getElementById('roundDisplay');
    if(rDisplay) rDisplay.innerText = data.round;

    const sDisplay = document.getElementById('songDisplay');
    const stLabel = document.getElementById('statusLabel');

    if (data.action === 'playing') {
        // STANJE: SVIRA -> POKRENI ANIMACIJU
        if(visContainer) visContainer.classList.remove('paused');
        
        if(sDisplay) {
            sDisplay.innerText = `${data.song_index}. PJESMA`;
            sDisplay.className = "display-1 fw-bold text-white mb-3 animate__animated animate__pulse";
        }
        if(stLabel) {
            stLabel.innerText = "SLUŠAJTE PAŽLJIVO...";
            stLabel.className = "text-danger fw-bold";
        }
        
    } else {
        // STANJE: PAUZA (između pjesama, ali prije timera)
        if(visContainer) visContainer.classList.add('paused');
        if(sDisplay) sDisplay.innerText = "PAUZA";
        if(stLabel) stLabel.innerText = "ČEKAM ADMINA...";
    }
});

// 2. Timer (POKREĆE SE NA KRAJU RUNDE)
socket.on('tv_start_timer', (data) => {
    // --- OVDJE JE PROMJENA ---
    // Sakrij pjesmu i vizualizator jer je runda gotova, sad se samo čeka timer
    document.getElementById('songDisplay').classList.add('d-none');
    document.getElementById('visualizer').classList.add('d-none');
    
    // Promijeni status
    const stLabel = document.getElementById('statusLabel');
    if(stLabel) {
        stLabel.innerText = "ZAVRŠAVANJE RUNDE!";
        stLabel.className = "text-danger fw-bold animate__animated animate__flash animate__infinite animate__slow";
    }

    // Pokaži Timer
    const timer = document.getElementById('timerOverlay');
    let sec = data.seconds || 30;
    
    timer.classList.remove('d-none');
    timer.innerText = sec;
    
    // Odbrojavanje
    const interval = setInterval(() => {
        sec--;
        timer.innerText = sec;
        if(sec <= 0) {
            clearInterval(interval);
            timer.classList.add('d-none');
        }
    }, 1000);
});

// 3. Zaključano (Nakon isteka timera)
socket.on('round_locked', () => {
    if(sfx.lock) sfx.lock.play().catch(()=>{});
    
    // Osiguraj da je timer skriven ako je ostao
    document.getElementById('timerOverlay').classList.add('d-none');
    
    // Sakrij vizualizator i pjesmu (za svaki slučaj)
    document.getElementById('visualizer').classList.add('d-none');
    document.getElementById('songDisplay').classList.add('d-none');

    // Ispiši status
    const stLabel = document.getElementById('statusLabel');
    if(stLabel) {
        stLabel.innerText = "RUNDA ZAKLJUČANA";
        stLabel.className = "text-warning fw-bold display-3"; // Povećan font
    }
});

// 4. Prikaz točnih odgovora
socket.on('screen_show_answers', (d) => {
    // Sakrij sve ostalo
    document.getElementById('visualizer').classList.add('d-none');
    document.getElementById('songDisplay').classList.add('d-none');
    document.getElementById('timerOverlay').classList.add('d-none');
    
    // Postavi naslov
    document.getElementById('statusLabel').innerText = "REZULTATI RUNDE";
    document.getElementById('statusLabel').className = "text-white fw-bold mb-4";
    
    // Prikaži container s odgovorima
    const c = document.getElementById('ansKey');
    c.classList.remove('d-none');
    
    // Generiraj HTML liste odgovora
    c.innerHTML = "";
    if(d.answers && d.answers.length > 0) {
        d.answers.forEach((a, i) => {
            // Dodajemo malu animaciju (fadeInUp) da ulaze jedan po jedan
            c.innerHTML += `
            <div class="d-flex align-items-center border-bottom border-secondary py-2 animate__animated animate__fadeInUp" style="animation-delay: ${i*0.1}s">
                <span class="badge bg-secondary me-3" style="min-width:40px">#${i+1}</span>
                <div class="lh-1 w-100">
                    <div class="text-warning fw-bold fs-3 text-truncate">${a.artist}</div>
                    <div class="text-white fs-5 text-truncate">${a.title}</div>
                </div>
            </div>`;
        });
    } else {
        c.innerHTML = "<div class='text-muted'>Nema podataka o odgovorima.</div>";
    }
});

// 5. Ažuriranje Top Liste
socket.on('update_leaderboard', (s) => {
    const c = document.getElementById('lbContent');
    if(!c) return;
    
    c.innerHTML = "";
    // Sortiraj po bodovima silazno
    const sorted = Object.entries(s).sort((a,b) => b[1] - a[1]);
    
    sorted.forEach(([name, score], i) => {
        let badgeClass = "bg-secondary";
        let rowClass = "";
        
        // Istakni prva tri mjesta
        if(i===0) { badgeClass = "bg-warning text-dark"; rowClass="border-warning border-start border-5"; }
        if(i===1) badgeClass = "bg-light text-dark";
        if(i===2) badgeClass = "bg-danger text-white";

        c.innerHTML += `
        <div class="lb-row text-white d-flex justify-content-between align-items-center ${rowClass} animate__animated animate__fadeInLeft" style="animation-duration:0.5s">
            <div class="text-truncate">
                <span class="badge ${badgeClass} rounded-pill me-3" style="width:40px">${i+1}</span>
                <span class="fw-bold">${name}</span>
            </div>
            <span class="fw-bold text-warning font-monospace fs-3 ms-2">${score}</span>
        </div>`;
    });
});

// --- PLAYER LISTENERS ---
socket.on('admin_player_list_full', (players) => {
    renderPlayers(players);
});

socket.on('admin_update_player_list', (players) => {
    renderPlayers(players);
});

function renderPlayers(players) {
    const container = document.getElementById('playersList');
    if(!container) return;
    container.innerHTML = '';

    if(!players || players.length === 0) {
        container.innerHTML = '<div class="text-muted small">Nema prijavljenih igrača.</div>';
        return;
    }

    // Prikaži svaki igrača kao veći badge s indikatorom statusa
    players.forEach(p => {
        const el = document.createElement('div');
        el.className = 'player';

        const dot = document.createElement('span');
        dot.className = 'dot';
        dot.title = p.status;
        updatePlayerDot(dot, p.status);

        const badge = document.createElement('span');
        badge.className = 'name-badge';
        badge.textContent = p.name;

        el.appendChild(dot);
        el.appendChild(badge);
        container.appendChild(el);
    });
}

function updatePlayerDot(el, status) {
    // keep a simple color mapping; visual effect handled by CSS
    if(status === 'active') el.style.backgroundColor = '#198754'; // success
    else if(status === 'away') el.style.backgroundColor = '#dc3545'; // danger
    else el.style.backgroundColor = '#6c757d'; // secondary
}