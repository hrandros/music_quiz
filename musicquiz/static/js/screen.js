const socket = io();

// Stanje ekrana
let timerInterval = null;
let currentRemaining = 0;
let currentTotal = 0;
let isPaused = false;

document.addEventListener("DOMContentLoaded", () => {
    console.log("📺 TV Screen Initialized");
    socket.emit('screen_ready');
});

// --- 1. KONTROLA PAUZE ---
socket.on('quiz_pause_state', (data) => {
    isPaused = data.paused;
    const vis = document.getElementById('visualizer');
    
    if (isPaused) {
        console.log("⏸️ Kviz pauziran");
        if (vis) vis.classList.add('paused');
        // Ne čistimo interval nego ga samo 'preskačemo' u startTimer logici
    } else {
        console.log("▶️ Kviz nastavljen");
        if (vis) vis.classList.remove('paused');
    }
});

// --- 2. NOVA PJESMA (ADMIN START) ---
socket.on('play_audio', (data) => {
    isPaused = false; // Reset pauze kod nove pjesme
    
    // UI Čišćenje
    document.getElementById('welcome-area')?.classList.add('d-none');
    document.getElementById('correct-answer-display').classList.add('d-none');
    document.getElementById('game-area').classList.remove('d-none');
    
    // Reset teksta i vizuala
    const songDisplay = document.getElementById('songDisplay');
    songDisplay.innerText = `${data.id || ''}. PJESMA U TIJEKU...`;
    songDisplay.classList.remove('d-none');
    
    document.getElementById('statusLabel').innerText = `RUNDA ${data.round || ''}`;
    
    const vis = document.getElementById('visualizer');
    if (vis) vis.classList.remove('d-none', 'paused');

    // Pokreni tajmer - koristi duration poslan s admin_events.py
    const duration = data.duration || 20; 
    document.getElementById('timerWrapper').classList.remove('d-none');
    startTimer(duration);
});

// --- 3. TOČAN ODGOVOR (KRAJ PJESME) ---
socket.on('screen_show_correct', (data) => {
    clearInterval(timerInterval);
    
    // Sakrij elemente igre
    document.getElementById('visualizer').classList.add('d-none');
    document.getElementById('songDisplay').classList.add('d-none');
    document.getElementById('statusLabel').innerText = `${data.id || ''}. PJESMA:`;
    
    // Pokaži odgovor
    const ansKey = document.getElementById('ansKey');
    const ansContainer = document.getElementById('correct-answer-display');
    document.getElementById('timerWrapper').classList.remove('d-none');
    startTimer(15);
    if (ansKey) {
        ansKey.innerText = `${data.artist} - ${data.title}`;
        ansKey.classList.remove('d-none');
    }
    ansContainer.classList.remove('d-none');
});

// --- 4. LEADERBOARD (Usklađeno sa screen_events.py) ---
socket.on('update_leaderboard', (data) => {
    const container = document.getElementById('leaderboard-body');
    if (!container) return;
    
    container.innerHTML = "";
    
    // Pretvaramo objekt u array i sortiramo po bodovima
    const players = Object.entries(data)
        .map(([name, score]) => ({ name, score }))
        .sort((a, b) => b.score - a.score);

    players.forEach((player, index) => {
        const row = document.createElement('div');
        row.className = "lb-row d-flex justify-content-between align-items-center animate__animated animate__fadeInUp";
        row.innerHTML = `
            <span>${index + 1}. ${player.name}</span>
            <span class="fw-bold text-warning">${player.score}</span>
        `;
        container.appendChild(row);
    });
});

// --- 5. PRIJAVE (WELCOME SCREEN) ---
socket.on('screen_show_welcome', (data) => {
    document.getElementById('game-area').classList.add('d-none');
    const welcomeArea = document.getElementById('welcome-area');
    if (welcomeArea) {
        welcomeArea.classList.remove('d-none');
        document.getElementById('welcome-msg').innerText = data.message;
        
        const qrDiv = document.getElementById("qrcode");
        if (qrDiv) {
            qrDiv.innerHTML = "";
            new QRCode(qrDiv, { text: data.url, width: 250, height: 250 });
        }
    }
});

// --- POMOĆNE FUNKCIJE ZA TAJMER ---

function startTimer(seconds) {
    clearInterval(timerInterval);
    currentRemaining = seconds;
    currentTotal = seconds;

    updateTimerUI();

    timerInterval = setInterval(() => {
        // AKO JE KVIZ PAUZIRAN, TAJMER STOJI
        if (!isPaused) {
            currentRemaining--;
            updateTimerUI();

            if (currentRemaining <= 0) {
                clearInterval(timerInterval);
            }
        }
    }, 1000);
}

function updateTimerUI() {
    const ring = document.getElementById('timerRing');
    const text = document.getElementById('timerVal');
    if (!ring || !text) return;

    const r = Math.max(0, currentRemaining);
    text.textContent = String(r);

    // SVG krug logika (C = 2 * r * PI)
    const C = 339.29; 
    const pct = r / currentTotal;
    ring.style.strokeDashoffset = C - (pct * C);

    // LOGIKA ZA BOJE:
    if (pct > 0.5) {
        // Više od 50% vremena - ZELENA
        ring.style.stroke = "#198754"; 
    } else if (pct > 0.2) {
        // Između 20% i 50% vremena - ŽUTA
        ring.style.stroke = "#ffc107";
    } else {
        // Ispod 20% vremena - CRVENA
        ring.style.stroke = "#dc3545";
    }
}