const socket = io();

// Stanje ekrana
let timerInterval = null;
let currentRemaining = 0;
let currentTotal = 0;
let isPaused = false;
let defaultGameAreaHtml = "";

document.addEventListener("DOMContentLoaded", () => {
    console.log("📺 TV Screen Initialized");
    socket.emit('screen_ready');

    const gameArea = document.getElementById('game-area');
    if (gameArea && !defaultGameAreaHtml) {
        defaultGameAreaHtml = gameArea.innerHTML;
    }
});

function restoreGameAreaLayout() {
    const gameArea = document.getElementById('game-area');
    if (!gameArea || !defaultGameAreaHtml) return;

    const hasCoreElements = gameArea.querySelector('#songDisplay') && gameArea.querySelector('#timerWrapper');
    if (!hasCoreElements) {
        gameArea.innerHTML = defaultGameAreaHtml;
    }
}

// --- KONTROLA PAUZE ---
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

// --- TIMER SYNCHRONIZATION FROM SERVER ---
socket.on('timer_update', (data) => {
    if (data && data.phase === 'answer_display') {
        return;
    }
    // Sync client timer with server time
    currentRemaining = data.remaining;
    currentTotal = data.total || currentTotal;
    updateTimerUI();
});

// --- 1.5 PRE-ROUND COUNTDOWN (30 SECONDS) ---
socket.on('round_countdown_start', (data) => {
    restoreGameAreaLayout();
    isPaused = false;

    const roundNum = data.round || 1;
    console.log(`⏲️ Runda ${roundNum} počinje za 30 sekundi...`);

    const roundDisplay = document.getElementById('roundDisplay');
    if (roundDisplay) roundDisplay.innerText = String(roundNum);

    // Show countdown using existing game-area layout
    document.getElementById('welcome-area')?.classList.add('d-none');
    document.getElementById('correct-answer-display')?.classList.add('d-none');
    document.getElementById('game-area')?.classList.remove('d-none');

    const songDisplay = document.getElementById('songDisplay');
    if (songDisplay) {
        songDisplay.innerText = `RUNDA ${roundNum} POČINJE...`;
        songDisplay.classList.remove('d-none');
    }

    const statusLabel = document.getElementById('statusLabel');
    if (statusLabel) {
        statusLabel.innerText = `RUNDA ${roundNum}`;
    }

    const vis = document.getElementById('visualizer');
    if (vis) vis.classList.add('d-none');

    const timerWrap = document.getElementById('timerWrapper');
    if (timerWrap) timerWrap.classList.remove('d-none');
    startTimer(30);
});


// --- 2. NOVA PJESMA (ADMIN START) ---
socket.on('play_audio', (data) => {
    restoreGameAreaLayout();
    isPaused = false; // Reset pauze kod nove pjesme

    // UI Čišćenje
    document.getElementById('welcome-area')?.classList.add('d-none');
    document.getElementById('correct-answer-display').classList.add('d-none');
    document.getElementById('game-area').classList.remove('d-none');

    // Reset teksta i vizuala
    const songDisplay = document.getElementById('songDisplay');
    const displayIndex = data.question_index || data.id || '';
    const questionType = data.question_type || "audio";
    if (songDisplay) {
        if (questionType === "text" || questionType === "text_multiple") {
            const questionText = data.question_text || 'PITANJE';
            songDisplay.innerHTML = `${displayIndex}. PITANJE U TIJEKU...<div class="text-warning mt-3">${questionText}</div>`;
        } else {
            songDisplay.innerText = `${displayIndex}. PITANJE U TIJEKU...`;
        }
    }
    songDisplay.classList.remove('d-none');

    document.getElementById('statusLabel').innerText = `RUNDA ${data.round || ''}`;

    const roundDisplay = document.getElementById('roundDisplay');
    if (roundDisplay && data.round) roundDisplay.innerText = String(data.round);

    // Pokreni tajmer - koristi duration poslan s admin_events.py
    const duration = data.duration || 20;
    document.getElementById('timerWrapper').classList.remove('d-none');
    startTimer(duration);

    // Handle media playback based on question type
    const questionTextEl = document.getElementById('questionText');
    const questionTextValue = document.getElementById('questionTextValue');

    if (questionTextEl) questionTextEl.classList.add('d-none');
    if (questionTextValue) questionTextValue.textContent = '';

    if ((questionType === "text" || questionType === "text_multiple") && questionTextEl && questionTextValue) {
        questionTextValue.textContent = data.question_text || 'PITANJE';
        questionTextEl.classList.add('d-none');
    }

    if (questionType === "simultaneous" && questionTextEl && questionTextValue) {
        questionTextValue.textContent = data.extra_question || data.question_text || 'PITANJE';
        questionTextEl.classList.remove('d-none');
    }

    if (questionType === "video") {
        // Hide audio visualizer, show video
        const vis = document.getElementById('visualizer');
        if (vis) vis.classList.add('d-none');

        const videoPlayer = document.getElementById('videoPlayer');
        if (videoPlayer) {
            videoPlayer.classList.remove('d-none');
            videoPlayer.src = data.url;
            videoPlayer.currentTime = data.start || 0;
            videoPlayer.volume = 0.8;

            videoPlayer.onloadedmetadata = function () {
                videoPlayer.play().catch(err => {
                    console.warn("Video playback failed:", err);
                });

                // Stop video after duration
                if (window.videoStopTimer) clearTimeout(window.videoStopTimer);
                window.videoStopTimer = setTimeout(() => {
                    videoPlayer.pause();
                }, (data.duration || 30) * 1000);
            };

            videoPlayer.onerror = function () {
                console.error("Video load error:", videoPlayer.error);
            };
        }
    } else {
        // Audio playback (original behavior)
        const vis = document.getElementById('visualizer');
        if (vis) {
            if (questionType === "text" || questionType === "text_multiple" || questionType === "simultaneous") {
                vis.classList.add('d-none');
            } else {
                vis.classList.remove('d-none', 'paused');
            }
        }

        const videoPlayer = document.getElementById('videoPlayer');
        if (videoPlayer) {
            videoPlayer.classList.add('d-none');
            videoPlayer.pause();
        }
    }
});

// --- 3. TOČAN ODGOVOR (KRAJ PJESME) ---
socket.on('screen_show_correct', (data) => {
    clearInterval(timerInterval);
    
    // Sakrij elemente igre
    document.getElementById('visualizer').classList.add('d-none');
    document.getElementById('songDisplay').classList.add('d-none');
    document.getElementById('questionText')?.classList.add('d-none');
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

// --- 6. ROUND SUMMARY (ALL CORRECT ANSWERS) ---
socket.on('screen_show_round_summary', (data) => {
    const roundNum = data.round;
    const songs = data.songs || [];

    const roundDisplay = document.getElementById('roundDisplay');
    if (roundDisplay) roundDisplay.innerText = String(roundNum || '');

    // Hide game area and show summary
    document.getElementById('game-area').classList.add('d-none');
    document.getElementById('welcome-area')?.classList.add('d-none');

    // Create round summary display
    const gameArea = document.getElementById('game-area');
    gameArea.classList.remove('d-none');
    gameArea.innerHTML = `
        <div class="text-center mt-4">
            <h1 class="text-warning fw-bold mb-4">RUNDA ${roundNum} - ZAVRŠENA!</h1>
            <div class="card bg-dark border-warning mt-4">
                <div class="card-header bg-warning text-dark fw-bold">TOČNI ODGOVORI</div>
                <div class="card-body p-0">
                    <div style="max-height: 70vh; overflow-y: auto;">
                        <table class="table table-dark table-sm mb-0">
                            <tbody>
                                ${songs.map((song) => {
                                    const answerText = song.artist
                                        ? `${song.artist} - ${song.title}`
                                        : `${song.title}`;
                                    return `
                                        <tr class="text-white small border-bottom border-secondary">
                                            <td class="ps-3 text-warning fw-bold" style="width: 80px;">#${song.question_position}</td>
                                            <td class="ps-2">${answerText}</td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    `;
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