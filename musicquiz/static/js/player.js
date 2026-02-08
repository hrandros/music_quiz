const socket = io();

// --- GLOBALNE VARIJABLE ---
let myName = "";
let currentQuestionId = null;
let currentQuestionType = "audio";  // Track question type
let questionStartTime = 0;  // When the question started (for time tracking)
let wakeLock = null;  // Wake Lock API reference
let isAnswerLocked = false;  // Anti-cheat: track if answers are locked
let cheatDetected = false;  // Track if cheating was detected


// --- INICIJALIZACIJA (QR KOD LOGIN ILI LOKALNO SAČUVANA PRIJAVA) ---
document.addEventListener("DOMContentLoaded", () => {
    // Provjeri ima li podataka u URL-u (od QR koda)
    const params = new URLSearchParams(window.location.search);
    const n = params.get('name');
    const p = params.get('pin');

    if (n) {
        // QR kod ima prioritet
        document.getElementById('username').value = n;
        if (p) document.getElementById('userpin').value = p;
        joinGame(); // Automatski pokušaj prijave
    } else {
        // Provjeri postoji li sačuvana prijava u localStorage
        const savedName = localStorage.getItem('playerName');
        const savedPin = localStorage.getItem('playerPin');

        if (savedName && savedPin) {
            document.getElementById('username').value = savedName;
            document.getElementById('userpin').value = savedPin;
            joinGame(); // Automatski pokušaj prijave sa sačuvanim kredencijama
        }
    }

    // Initialize anti-cheat systems
    initAntiCheat();
    initWakeLock();
});

// --- LOGIKA PRIJAVE ---
function joinGame() {
    const n = document.getElementById('username').value.trim();
    const p = document.getElementById('userpin').value.trim();
    const err = document.getElementById('login-error');
    const joinBtn = document.getElementById('join-btn');
    const joinBtnText = document.getElementById('join-btn-text');
    const joinBtnLoading = document.getElementById('join-btn-loading');
    const errorMsg = document.getElementById('error-message');

    // Clear previous errors
    err.classList.add('d-none');
    errorMsg.innerText = '';

    if (!n) {
        err.classList.remove('d-none');
        errorMsg.innerText = 'Unesi ime tima!';
        return;
    }

    if (!p || p.length !== 4) {
        err.classList.remove('d-none');
        errorMsg.innerText = 'Unesi važeći 4-znamenkasti PIN!';
        return;
    }

    // Show loading state
    joinBtn.disabled = true;
    joinBtnText.classList.add('d-none');
    joinBtnLoading.classList.remove('d-none');

    socket.emit('player_join', { name: n, pin: p });
}

socket.on('join_success', d => {
    myName = d.name;

    // Spremi kredencijale u localStorage za buduće sesije
    const n = document.getElementById('username').value.trim();
    const p = document.getElementById('userpin').value.trim();
    localStorage.setItem('playerName', n);
    localStorage.setItem('playerPin', p);

    document.getElementById('login-screen').classList.add('d-none');
    document.getElementById('game-screen').classList.remove('d-none');
    document.getElementById('player-name-display').innerText = myName;

    // Ako nema aktivne pjesme, prikaži poruku
    document.getElementById('answer-sheet').innerHTML = `
        <div class="text-center text-muted mt-5 fade-in">
            <i class="bi bi-music-note-beamed fs-1"></i><br>
            Čekam početak pjesme...
        </div>`;

    // Request wake lock after successful join
    requestWakeLock();
});

socket.on('join_error', d => {
    const joinBtn = document.getElementById('join-btn');
    const joinBtnText = document.getElementById('join-btn-text');
    const joinBtnLoading = document.getElementById('join-btn-loading');
    const e = document.getElementById('login-error');
    const errorMsg = document.getElementById('error-message');

    // Reset loading state
    joinBtn.disabled = false;
    joinBtnText.classList.remove('d-none');
    joinBtnLoading.classList.add('d-none');

    // Show error message
    e.classList.remove('d-none');
    errorMsg.innerText = d.msg || 'Greška pri pridruživanju. Pokušaj ponovno.';

    // Vrati login ekran ako je bio sakriven
    document.getElementById('login-screen').classList.remove('d-none');
    document.getElementById('game-screen').classList.add('d-none');
});

socket.on('update_leaderboard', (allScores) => {
    if (myName && allScores[myName] !== undefined) {
        document.getElementById('my-score').innerText = allScores[myName];
    }
});

function renderAnswerResult(data) {
    document.getElementById('answer-sheet').classList.add('d-none');
    document.getElementById('graded-answer-display').classList.remove('d-none');
    document.getElementById('lock-overlay').classList.add('d-none');
    document.getElementById('cheat-warning-overlay').classList.add('d-none');
    cheatDetected = false;

    let playerAnswerText = "Nema odgovora";
    if (currentQuestionType === "audio" || currentQuestionType === "video") {
        playerAnswerText = `${data.player_answer.artist || "?"} - ${data.player_answer.title || "?"}`;
    } else if (currentQuestionType === "text") {
        playerAnswerText = data.player_answer.title || "Nema odgovora";
    } else if (currentQuestionType === "text_multiple") {
        const choiceIdx = data.player_answer.choice;
        playerAnswerText = choiceIdx >= 0 ? data.choices[choiceIdx] || "Nema odgovora" : "Nema odgovora";
    } else if (currentQuestionType === "simultaneous") {
        playerAnswerText = `${data.player_answer.artist || "?"} - ${data.player_answer.title || "?"}<br><small>${data.player_answer.extra || "?"}</small>`;
    }

    let correctAnswerText = "?";
    if (currentQuestionType === "audio" || currentQuestionType === "video") {
        correctAnswerText = `${data.correct_answer.artist} - ${data.correct_answer.title}`;
    } else if (currentQuestionType === "text") {
        correctAnswerText = data.correct_answer.title || "?";
    } else if (currentQuestionType === "text_multiple") {
        correctAnswerText = data.correct_answer.choice || "?";
    } else if (currentQuestionType === "simultaneous") {
        correctAnswerText = `${data.correct_answer.artist} - ${data.correct_answer.title}<br><small>${data.correct_answer.extra || ""}</small>`;
    }

    document.getElementById('player-answer').innerHTML = playerAnswerText;
    document.getElementById('correct-answer').innerHTML = correctAnswerText;

    const pointsEarned = (data.artist_points || 0) + (data.title_points || 0) + (data.extra_points || 0);
    document.getElementById('points-earned').innerText = pointsEarned.toFixed(1);

    const maxPoints = typeof data.max_points === 'number' ? data.max_points : 2;
    const totalEl = document.getElementById('points-total');
    if (totalEl) totalEl.innerText = `/${maxPoints}`;
}

// --- GLAVNA LOGIKA IGRE ---

// 1. Nova pjesma počinje -> Otključaj i prikaži polja prema tipu pitanja
socket.on('player_unlock_input', (data) => {
    currentQuestionId = data.question_id;
    currentQuestionType = data.question_type || "audio";  // Default to audio
    questionStartTime = data.question_started_at || (Date.now() / 1000);  // Record start time in seconds
    isAnswerLocked = false;  // Reset lock state for new question
    cheatDetected = false;  // Reset cheat detection

    // Sakrij overlay "Zaključano" i prikaži input sheet
    document.getElementById('lock-overlay').classList.add('d-none');
    document.getElementById('cheat-warning-overlay').classList.add('d-none');
    document.getElementById('answer-sheet').classList.remove('d-none');
    document.getElementById('graded-answer-display').classList.add('d-none');
    const sheet = document.getElementById('answer-sheet');
    let inputsHtml = "";

    if (currentQuestionType === "audio" || currentQuestionType === "video") {
        inputsHtml = `
            <div class="mb-3">
                <label class="text-secondary small ms-1">IZVOĐAČ / ARTIST</label>
                <input type="text" id="inpArtist" class="form-control form-control-lg bg-dark text-white border-secondary"
                       placeholder="..." autocomplete="off">
            </div>
            <div class="mb-4">
                <label class="text-secondary small ms-1">NAZIV PJESME / TITLE</label>
                <input type="text" id="inpTitle" class="form-control form-control-lg bg-dark text-white border-secondary"
                       placeholder="..." autocomplete="off">
            </div>
        `;
    } else if (currentQuestionType === "text") {
        inputsHtml = `
            <div class="mb-3">
                <label class="text-secondary small ms-1">${data.question_text || "PITANJE"}</label>
                <input type="text" id="inpAnswer" class="form-control form-control-lg bg-dark text-white border-secondary"
                       placeholder="..." autocomplete="off">
            </div>
        `;
    } else if (currentQuestionType === "text_multiple") {
        const choices = data.choices || [];
        inputsHtml = `
            <div class="mb-4">
                <label class="text-secondary small ms-1 d-block mb-3">${data.question_text || "ODABERI ODGOVOR"}</label>
                <div class="choice-group">
        `;
        choices.forEach((choice, idx) => {
            inputsHtml += `
                <div class="mb-2">
                    <input type="radio" id="choice${idx}" name="choice" value="${idx}" class="choice-radio">
                    <label for="choice${idx}" class="choice-label form-control form-control-lg bg-dark text-white border-secondary">
                        ${choice}
                    </label>
                </div>
            `;
        });
        inputsHtml += `</div></div>`;
    } else if (currentQuestionType === "simultaneous") {
        inputsHtml = `
            <div class="mb-3">
                <label class="text-secondary small ms-1">IZVOĐAČ / ARTIST</label>
                <input type="text" id="inpArtist" class="form-control form-control-lg bg-dark text-white border-secondary"
                       placeholder="..." autocomplete="off">
            </div>
            <div class="mb-3">
                <label class="text-secondary small ms-1">NAZIV PJESME / TITLE</label>
                <input type="text" id="inpTitle" class="form-control form-control-lg bg-dark text-white border-secondary"
                       placeholder="..." autocomplete="off">
            </div>
            <div class="mb-4">
                <label class="text-secondary small ms-1">${data.extra_question || "DODATNO PITANJE"}</label>
                <input type="text" id="inpExtra" class="form-control form-control-lg bg-dark text-white border-secondary"
                       placeholder="..." autocomplete="off">
            </div>
        `;
    }

    sheet.innerHTML = `
        <div class="animate-fade-in mt-4">
            <h4 class="text-center text-warning mb-4">
                <span class="badge bg-danger me-2">RUNDA ${data.round}</span>
                PITANJE #${data.question_index}
            </h4>
            ${inputsHtml}
            <button id="submit-btn" class="btn btn-success btn-lg w-100 fw-bold mt-4"
                    onclick="submitAnswer()"
                    aria-label="Pošalji odgovor">
                <i class="bi bi-send-fill me-2" aria-hidden="true"></i>
                POŠALJI ODGOVOR
            </button>
            <div class="text-center mt-3" style="min-height: 24px;">
                 <small id="save-status" class="text-success fw-bold opacity-0 transition-opacity">
                    <i class="bi bi-cloud-check-fill"></i> SPREMLJENO
                 </small>
            </div>
        </div>
    `;

    // Setup event listeners based on type
    if (currentQuestionType === "text_multiple") {
        // For multiple choice, submit on button click or automatically submit when locked
        const radios = document.querySelectorAll('.choice-radio');
        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                // User can also submit via button
            });
        });
    } else {
        // For text inputs, submit on Enter key or button click
        const inputs = document.querySelectorAll('input[type="text"]');
        inputs.forEach(inp => {
            inp.addEventListener('keypress', (e) => {
                if (e.key === "Enter") {
                    submitAnswer();
                    inp.blur();
                }
            });
        });
    }

    // Focus first input
    const firstInput = document.querySelector('input[type="text"]');
    if (firstInput) setTimeout(() => firstInput.focus(), 100);
});

// 2. Kraj vremena -> Zaključaj
socket.on('player_lock_input', () => {
    isAnswerLocked = true;  // Mark as locked

    // Auto-submit the current answer before forcing UI lock state
    submitAnswer(true);

    // Disable input fields
    const i1 = document.getElementById('inpArtist');
    const i2 = document.getElementById('inpTitle');
    const i4 = document.getElementById('inpAnswer');
    const i5 = document.getElementById('inpExtra');
    const radios = document.querySelectorAll('input[type="radio"]');

    [i1, i2, i4, i5].forEach(inp => {
        if (inp) inp.disabled = true;
    });
    radios.forEach(radio => {
        radio.disabled = true;
    });

    // Disable and update submit button
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn && !submitBtn.disabled) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="bi bi-lock-fill me-2" aria-hidden="true"></i>ZAKLJUČANO';
        submitBtn.classList.remove('btn-success');
        submitBtn.classList.add('btn-secondary');
    }
});

// 3. Prikaži bodovanu točnu odpor nakon što je zaključano
socket.on('player_show_answer', (data) => {
    renderAnswerResult(data);
});

// 3. Funkcija za slanje podataka serveru
function submitAnswer(forceSubmit = false) {
    if (!currentQuestionId || !myName) return;
    if (cheatDetected && !isAnswerLocked && !forceSubmit) return; // Prevent submission if cheating detected

    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn && submitBtn.disabled) return; // Locked

    // Calculate submission time (in seconds from question start)
    const submissionTime = (Date.now() / 1000) - questionStartTime;

    let answerData = {
        player_name: myName,
        question_id: currentQuestionId,
        question_type: currentQuestionType,
        submission_time: submissionTime,
        artist: "",
        title: "",
        extra: "",
        choice: -1
    };

    // Collect answers based on question type
    if (currentQuestionType === "audio" || currentQuestionType === "video") {
        answerData.artist = document.getElementById('inpArtist')?.value || "";
        answerData.title = document.getElementById('inpTitle')?.value || "";
    } else if (currentQuestionType === "text") {
        answerData.title = document.getElementById('inpAnswer')?.value || "";
    } else if (currentQuestionType === "text_multiple") {
        const selected = document.querySelector('input[name="choice"]:checked');
        answerData.choice = selected ? parseInt(selected.value) : -1;
    } else if (currentQuestionType === "simultaneous") {
        answerData.artist = document.getElementById('inpArtist')?.value || "";
        answerData.title = document.getElementById('inpTitle')?.value || "";
        answerData.extra = document.getElementById('inpExtra')?.value || "";
    }

    socket.emit('player_submit_answer', answerData);

    // Display visual confirmation
    if (submitBtn) {
        submitBtn.innerHTML = '<i class="bi bi-check-circle-fill me-2" aria-hidden="true"></i>POSLANO';
        submitBtn.classList.remove('btn-secondary');
        submitBtn.classList.add('btn-success');
    }

    // Show saved status
    const status = document.getElementById('save-status');
    if (status) status.style.opacity = '1';
}

// --- LOGOUT FUNCTION ---
function logout() {
    // Obriši sačuvane kredencijale
    localStorage.removeItem('playerName');
    localStorage.removeItem('playerPin');

    // Resetuj globalne varijable
    myName = "";
    currentQuestionId = null;
    isAnswerLocked = false;
    cheatDetected = false;

    // Release wake lock
    releaseWakeLock();

    // Prikaži login screen
    document.getElementById('game-screen').classList.add('d-none');
    document.getElementById('login-screen').classList.remove('d-none');
    document.getElementById('answer-sheet').innerHTML = '';
    document.getElementById('graded-answer-display').classList.add('d-none');
    document.getElementById('lock-overlay').classList.add('d-none');
    document.getElementById('cheat-warning-overlay').classList.add('d-none');

    // Očisti input polja
    document.getElementById('username').value = '';
    document.getElementById('userpin').value = '';

    // Prekinuti socket konekciju i ponovo se spojiti
    socket.disconnect();
    socket.connect();
}

// --- WAKE LOCK API (Prevent Screen Sleep) ---
function initWakeLock() {
    // Check if Wake Lock API is supported
    if (!('wakeLock' in navigator)) {
        console.log('Wake Lock API not supported');
        return;
    }
}

async function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;

    try {
        wakeLock = await navigator.wakeLock.request('screen');
        console.log('Wake Lock activated - screen will stay awake');

        wakeLock.addEventListener('release', () => {
            console.log('Wake Lock released');
        });
    } catch (err) {
        console.error(`Wake Lock error: ${err.name}, ${err.message}`);
    }
}

function releaseWakeLock() {
    if (wakeLock !== null) {
        wakeLock.release()
            .then(() => {
                wakeLock = null;
                console.log('Wake Lock manually released');
            });
    }
}

// Re-request wake lock when page becomes visible again
document.addEventListener('visibilitychange', () => {
    if (wakeLock !== null && document.visibilityState === 'visible') {
        requestWakeLock();
    }
});

// --- ANTI-CHEAT SYSTEM ---
function initAntiCheat() {
    let keyboardCooldownUntil = 0;

    const isKeyboardLikelyOpen = () => {
        const active = document.activeElement;
        if (!active) return false;
        const isTextInput = active.tagName === 'INPUT' || active.tagName === 'TEXTAREA';
        if (!isTextInput) return false;

        if (window.visualViewport) {
            return window.visualViewport.height < window.innerHeight * 0.8;
        }

        return false;
    };

    const extendKeyboardCooldown = (ms = 600) => {
        const until = Date.now() + ms;
        if (until > keyboardCooldownUntil) {
            keyboardCooldownUntil = until;
        }
    };

    const isKeyboardCooldownActive = () => Date.now() < keyboardCooldownUntil;

    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', () => {
            extendKeyboardCooldown(800);
        });
    }

    document.addEventListener('focusin', (e) => {
        const target = e.target;
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
            extendKeyboardCooldown(800);
        }
    });

    document.addEventListener('focusout', (e) => {
        const target = e.target;
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
            extendKeyboardCooldown(800);
        }
    });

    // Detect window blur (switching to another window/tab)
    window.addEventListener('blur', () => {
        if (currentQuestionId && !isAnswerLocked && myName) {
            handleCheatDetection('Prebačeno na drugi prozor ili aplikaciju');
        }
    });

    // Detect when window becomes focused again
    window.addEventListener('focus', () => {
        if (currentQuestionId && !isAnswerLocked && cheatDetected) {
            // Give a grace period of 2 seconds before unlocking
            setTimeout(() => {
                if (document.hasFocus()) {
                    clearCheatWarning();
                }
            }, 2000);
        }
    });

    // Detect split-screen mode by monitoring window size changes
    let lastWidth = window.innerWidth;
    let lastHeight = window.innerHeight;

    window.addEventListener('resize', () => {
        if (!currentQuestionId || isAnswerLocked || !myName) return;
        if (isKeyboardLikelyOpen()) return;
        if (isKeyboardCooldownActive()) return;

        const currentWidth = window.innerWidth;
        const currentHeight = window.innerHeight;
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;

        // Detect if window is significantly smaller than screen (split-screen)
        // Allow for some browser UI (toolbars, etc.)
        const widthRatio = currentWidth / screenWidth;
        const heightRatio = currentHeight / screenHeight;

        // If window is less than 85% of screen width or height, consider it split-screen
        if (widthRatio < 0.85 || heightRatio < 0.85) {
            handleCheatDetection('Prozor u split-screen načinu rada');
        } else if (cheatDetected && widthRatio >= 0.85 && heightRatio >= 0.85) {
            // Window was maximized again
            clearCheatWarning();
        }

        lastWidth = currentWidth;
        lastHeight = currentHeight;
    });

    // Also check visibility changes
    document.addEventListener('visibilitychange', () => {
        if (myName) {
            socket.emit('player_activity_status', {
                name: myName,
                status: document.hidden ? 'away' : 'active'
            });
        }

        if (document.hidden && currentQuestionId && !isAnswerLocked) {
            handleCheatDetection('Kartica skrivena (prebačeno na drugu karticu)');
        } else if (!document.hidden && cheatDetected && currentQuestionId && !isAnswerLocked) {
            // Give grace period when returning
            setTimeout(() => {
                if (!document.hidden) {
                    clearCheatWarning();
                }
            }, 2000);
        }
    });
}

function handleCheatDetection(reason) {
    if (cheatDetected) return; // Already detected

    cheatDetected = true;
    console.log('Anti-cheat triggered:', reason);

    // Show warning overlay
    const overlay = document.getElementById('cheat-warning-overlay');
    const reasonElement = document.getElementById('cheat-reason');
    if (overlay) {
        overlay.classList.remove('d-none');
        if (reasonElement) {
            reasonElement.textContent = reason;
        }
    }

    // Disable all inputs
    const inputs = document.querySelectorAll('input[type="text"], input[type="radio"]');
    inputs.forEach(inp => {
        inp.disabled = true;
    });

    // Disable submit button
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.classList.remove('btn-success');
        submitBtn.classList.add('btn-danger');
    }

    // Notify server about cheating attempt
    if (myName && currentQuestionId) {
        socket.emit('player_cheat_detected', {
            player_name: myName,
            question_id: currentQuestionId,
            reason: reason,
            timestamp: Date.now()
        });
    }
}

function clearCheatWarning() {
    if (!cheatDetected) return;

    console.log('Clearing anti-cheat warning');
    cheatDetected = false;

    // Hide warning overlay
    const overlay = document.getElementById('cheat-warning-overlay');
    if (overlay) {
        overlay.classList.add('d-none');
    }

    // Re-enable inputs if question is still active
    if (currentQuestionId && !isAnswerLocked) {
        const inputs = document.querySelectorAll('input[type="text"], input[type="radio"]');
        inputs.forEach(inp => {
            inp.disabled = false;
        });

        // Re-enable submit button
        const submitBtn = document.getElementById('submit-btn');
        if (submitBtn && !submitBtn.disabled) {
            submitBtn.classList.remove('btn-danger');
            submitBtn.classList.add('btn-success');
        }
    }
}

// --- ROUND SUMMARY FOR PLAYER ---
socket.on('player_show_round_summary', (data) => {
    const roundNum = data.round;
    const answers = data.answers || [];

    // Hide answer sheet and graded answer display
    document.getElementById('answer-sheet').classList.add('d-none');
    document.getElementById('graded-answer-display').classList.add('d-none');
    document.getElementById('lock-overlay').classList.add('d-none');
    document.getElementById('cheat-warning-overlay').classList.add('d-none');
    cheatDetected = false;  // Reset for next round

    // Create round summary container if it doesn't exist
    let summaryDiv = document.getElementById('round-summary-display');
    if (!summaryDiv) {
        summaryDiv = document.createElement('div');
        summaryDiv.id = 'round-summary-display';
        document.getElementById('game-screen').appendChild(summaryDiv);
    }

    // Display round summary
    summaryDiv.className = 'mt-4';
    summaryDiv.innerHTML = `
        <h3 class="text-center text-warning fw-bold mb-4">RUNDA ${roundNum} - ZAVRŠENA!</h3>
        <div class="card bg-dark border-warning mb-4">
            <div class="card-header bg-warning text-dark fw-bold text-center py-2">
                TVA BODOVANJA ZA RUNDU
            </div>
            <div class="card-body p-0">
                <div style="max-height: 50vh; overflow-y: auto;">
                    ${answers.map((ans, idx) => {
                        const total = (ans.artist_points || 0) + (ans.title_points || 0) + (ans.extra_points || 0);
                        const maxPoints = ans.max_points || 2;
                        const extraRow = ans.question_type === 'simultaneous' ? `
                            <div class="row mb-2">
                                <div class="col-6">
                                    <small class="text-muted d-block mb-1">TVOJ DODATNI ODGOVOR</small>
                                    <small class="text-white">${ans.extra_guess || '-'}</small>
                                </div>
                                <div class="col-6 text-end">
                                    <small class="text-muted d-block mb-1">TOČAN DODATNI ODGOVOR</small>
                                    <small class="text-success">${ans.correct_extra || '-'}</small>
                                </div>
                            </div>
                        ` : '';
                        return `
                            <div class="border-bottom border-secondary p-3">
                                <h6 class="text-warning mb-2">PITANJE ${ans.question_position}</h6>
                                <div class="row mb-3">
                                    <div class="col-6">
                                        <small class="text-muted d-block mb-1">TVOJ ODGOVOR</small>
                                        <small class="text-white">${ans.artist_guess} - ${ans.title_guess}</small>
                                    </div>
                                    <div class="col-6 text-end">
                                        <small class="text-muted d-block mb-1">TOČAN ODGOVOR</small>
                                        <small class="text-success">${ans.correct_artist} - ${ans.correct_title}</small>
                                    </div>
                                </div>
                                ${extraRow}
                                <div class="progress mb-2" style="height: 1.5rem;">
                                    <div class="progress-bar bg-warning text-dark fw-bold" style="width: ${(total / maxPoints) * 100}%">
                                        ${total.toFixed(1)}/${maxPoints}
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        </div>
    `;
});