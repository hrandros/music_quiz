const socket = io();
const sfx = {
    correct: new Audio('/static/sfx/correct.mp3'),
    lock: new Audio('/static/sfx/lock.mp3')
};

// --- LISTENERS ---

document.addEventListener("DOMContentLoaded", () => {
    // Javi serveru da je TV ekran upaljen i da treba inicijalnu listu
    socket.emit('screen_ready');
});

// 1. Ažuriranje statusa (Nova pjesma)
socket.on('screen_update_status', (data) => {
    // Reset prikaza (sakrij odgovore, pokaži glavni info)
    document.getElementById('ansKey').classList.add('d-none');
    
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
    // Circular SVG timer: drives stroke and numeric center
    const wrapper = document.getElementById('timerWrapper');
    const ring = document.getElementById('timerRing');
    const val = document.getElementById('timerValue');
    if(!wrapper || !ring || !val) return;

    const total = parseInt(data.seconds || 30, 10);
    let remaining = total;

    // svg circle circumference for r=45 -> 2*pi*r
    const C = 2 * Math.PI * 45; // ~282.743
    ring.style.strokeDasharray = C;
    ring.style.transition = 'stroke-dashoffset 0.4s linear';

    wrapper.classList.remove('d-none');
    val.innerText = remaining;

    // ensure visible elements
    const visContainer = document.getElementById('visualizer');
    if(visContainer) visContainer.classList.remove('d-none');
    document.getElementById('songDisplay').classList.remove('d-none');

    const stLabel = document.getElementById('statusLabel');
    if(stLabel) { stLabel.innerText = "PJEVAJTE / SLUŠAJTE"; stLabel.className = "text-danger fw-bold"; }

    // initial progress (full ring)
    ring.style.strokeDashoffset = 0;

    // keep a local timer as fallback; real value should come from server 'timer_tick'
    if(window.__screen_timer_interval) clearInterval(window.__screen_timer_interval);
    window.__screen_timer_interval = setInterval(() => {
        remaining--;
        if(remaining < 0) remaining = 0;
        updateRing(remaining, total, C, ring, val);
        if(remaining <= 0) {
            clearInterval(window.__screen_timer_interval);
        }
    }, 1000);
});

// server can also emit per-second ticks; prefer those when available
socket.on('timer_tick', (d) => {
    const wrapper = document.getElementById('timerWrapper');
    const ring = document.getElementById('timerRing');
    const val = document.getElementById('timerValue');
    if(!wrapper || !ring || !val) return;
    wrapper.classList.remove('d-none');

    const sec = parseInt(d.sec || 0, 10);
    // try to read stored total from wrapper dataset
    const total = parseInt(wrapper.dataset.total || sec, 10);
    // compute circumference
    const C = 2 * Math.PI * 45;
    updateRing(sec, total, C, ring, val);
});

// 3. Zaključano (Nakon isteka timera)
socket.on('round_locked', () => {
    if(sfx.lock) sfx.lock.play().catch(()=>{});
    
    // Osiguraj da je timer skriven ako je ostao
    const wrapper = document.getElementById('timerWrapper');
    if(wrapper) wrapper.classList.add('d-none');
    if(window.__screen_timer_interval) { clearInterval(window.__screen_timer_interval); window.__screen_timer_interval = null; }
    
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
socket.on('screen_show_correct', (data) => {
    // 1. Sakrij vizualizator i timer
    document.getElementById('visualizer').classList.add('d-none');
    const timerWrapper = document.getElementById('timerWrapper');
    if(timerWrapper) timerWrapper.classList.add('d-none');

    // 2. Postavi status labelu
    const stLabel = document.getElementById('statusLabel');
    if(stLabel) {
        stLabel.innerText = "TOČAN ODGOVOR:";
        stLabel.className = "text-white fw-bold mb-2";
    }

    // 3. Prikaži rješenje u ansKey kontejneru (ili stvori novi namjenski div)
    const c = document.getElementById('ansKey');
    c.classList.remove('d-none');
    c.innerHTML = `
        <div class="text-center animate__animated animate__zoomIn">
            <div class="text-warning fw-bold display-2">${data.artist}</div>
            <div class="text-white display-4">${data.title}</div>
        </div>
    `;

});

// 5. Ažuriranje Top Liste
socket.on('update_leaderboard', (s) => {
    const c = document.getElementById('lbContent');
    if(!c) return;
    
    // capture previous order
    const prev = Array.from(c.querySelectorAll('.lb-row .fw-bold')).map(el => el.innerText);
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

        // stagger animations to emphasize reordering
        c.innerHTML += `
        <div class="lb-row text-white d-flex justify-content-between align-items-center ${rowClass} animate__animated animate__fadeInDown" style="animation-duration:0.5s; animation-delay:${i*0.08}s">
            <div class="text-truncate">
                <span class="badge ${badgeClass} rounded-pill me-3" style="width:40px">${i+1}</span>
                <span class="fw-bold">${name}</span>
            </div>
            <span class="fw-bold text-warning font-monospace fs-3 ms-2">${score}</span>
        </div>`;
    });

    // simple visual cue for changed ordering: pulse items that moved
    setTimeout(() => {
        const newOrder = Array.from(c.querySelectorAll('.lb-row .fw-bold')).map(el => el.innerText);
        newOrder.forEach((n, idx) => {
            if(prev.indexOf(n) !== idx) {
                const row = c.querySelectorAll('.lb-row')[idx];
                if(row) row.classList.add('animate__animated','animate__pulse');
            }
        });
    }, 600);
});

// 6. Reprodukcija audio zapisa (POKREĆE SE NA POČETKU PJESME) - priprema za sljedeću pjesmu
socket.on('play_audio', (data) => {
    // 1. Sakrij prethodno rješenje
    document.getElementById('ansKey').classList.add('d-none');
    
    // 2. Pokaži vizualizator
    document.getElementById('visualizer').classList.remove('d-none');
    
    // 3. Ažuriraj tekst o pjesmi
    const sDisplay = document.getElementById('songDisplay');
    if(sDisplay) {
        sDisplay.innerText = `${data.song_index}. PJESMA`;
        sDisplay.classList.remove('d-none');
    }
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

// Helper to update circular ring and numeric value
function updateRing(remaining, total, C, ringEl, valEl) {
    if(!ringEl || !valEl) return;
    const r = Math.max(0, Math.min(remaining, total));
    valEl.innerText = r;
    const frac = total > 0 ? (1 - (r / total)) : 1;
    const offset = Math.round(C * frac);
    // set strokeDashoffset so ring 'empties' clockwise
    ringEl.style.strokeDashoffset = offset;
}

let qrGenerator = null;

// Kada admin otvori prijave
socket.on('screen_show_welcome', (data) => {
    // 1. Sakrij područje igre, prikaži područje dobrodošlice
    document.getElementById('game-area').classList.add('d-none');
    document.getElementById('welcome-area').classList.remove('d-none');
    
    // 2. Postavi poruku
    document.getElementById('welcome-msg').innerText = data.message;
    
    // 3. Generiraj QR kod ako već nije generiran
    const qrDiv = document.getElementById("qrcode");
    qrDiv.innerHTML = ""; 
    new QRCode(qrDiv, {
        text: data.url,
        width: 250,
        height: 250
    });
});

// Kada admin zatvori prijave ili krene prva pjesma
socket.on('screen_hide_welcome', () => {
    document.getElementById('welcome-area').classList.add('d-none');
    document.getElementById('game-area').classList.remove('d-none');
});

// Automatsko prebacivanje čim krene audio (za svaki slučaj)
socket.on('play_audio', () => {
    document.getElementById('welcome-area').classList.add('d-none');
    document.getElementById('game-area').classList.remove('d-none');
    
    // Pokreni vizualizator
    document.getElementById('visualizer').classList.remove('paused');
});