const socket = io();

// --- GLOBALNE VARIJABLE ---
let myName = "";
let currentSongId = null;
let saveTimeout = null;

// --- INICIJALIZACIJA (QR KOD LOGIN) ---
document.addEventListener("DOMContentLoaded", () => {
    // Provjeri ima li podataka u URL-u (od QR koda)
    const params = new URLSearchParams(window.location.search);
    const n = params.get('name');
    const p = params.get('pin');

    if (n) {
        document.getElementById('username').value = n;
        if (p) document.getElementById('userpin').value = p;
        joinGame(); // Automatski pokušaj prijave
    }
});

// --- LOGIKA PRIJAVE ---
function joinGame() {
    const n = document.getElementById('username').value.trim();
    const p = document.getElementById('userpin').value.trim();
    const err = document.getElementById('login-error');

    if (!n) {
        err.classList.remove('d-none');
        err.innerText = "Unesi ime tima!";
        return;
    }
    socket.emit('update_leaderboard');
    socket.emit('player_join', { name: n, pin: p });
}

socket.on('join_success', d => {
    myName = d.name;
    document.getElementById('login-screen').classList.add('d-none');
    document.getElementById('game-screen').classList.remove('d-none');
    document.getElementById('player-name-display').innerText = myName;
    
    // Ako nema aktivne pjesme, prikaži poruku
    document.getElementById('answer-sheet').innerHTML = `
        <div class="text-center text-muted mt-5 fade-in">
            <i class="bi bi-music-note-beamed fs-1"></i><br>
            Čekam početak pjesme...
        </div>`;
});

socket.on('join_error', d => {
    const e = document.getElementById('login-error');
    e.classList.remove('d-none');
    e.innerText = d.msg;
    // Vrati login ekran ako je bio sakriven
    document.getElementById('login-screen').classList.remove('d-none');
    document.getElementById('game-screen').classList.add('d-none');
});

socket.on('update_leaderboard', (allScores) => {
    if (myName && allScores[myName] !== undefined) {
        document.getElementById('my-score').innerText = allScores[myName];
    }
});

// --- GLAVNA LOGIKA IGRE ---

// 1. Nova pjesma počinje -> Otključaj i prikaži polja
socket.on('player_unlock_input', (data) => {
    currentSongId = data.song_id;

    // Sakrij overlay "Zaključano"
    document.getElementById('lock-overlay').classList.add('d-none');

    const sheet = document.getElementById('answer-sheet');
    
    // Generiraj HTML ovisno o podacima (ako šaljemo tip pjesme)
    let inputsHtml = `
        <div class="mb-3">
            <label class="text-secondary small ms-1">IZVOĐAČ</label>
            <input type="text" id="inpArtist" class="form-control form-control-lg bg-dark text-white border-secondary" 
                   placeholder="..." autocomplete="off">
        </div>
        <div class="mb-4">
            <label class="text-secondary small ms-1">NAZIV PJESME</label>
            <input type="text" id="inpTitle" class="form-control form-control-lg bg-dark text-white border-secondary" 
                   placeholder="..." autocomplete="off">
        </div>
    `;

    sheet.innerHTML = `
        <div class="animate-fade-in mt-4">
            <h4 class="text-center text-warning mb-4">
                <span class="badge bg-danger me-2">RUNDA ${data.round}</span> 
                PJESMA #${data.song_index}
            </h4>
            ${inputsHtml}
            <div class="text-center mt-3" style="min-height: 24px;">
                 <small id="save-status" class="text-success fw-bold opacity-0 transition-opacity">
                    <i class="bi bi-cloud-check-fill"></i> SPREMLJENO
                 </small>
            </div>
        </div>
    `;

    // Fokusiraj prvo polje
    const inpArt = document.getElementById('inpArtist');
    const inpTit = document.getElementById('inpTitle');
    setTimeout(() => inpArt.focus(), 100);

    // Event listeneri za Auto-Save
    const handleInput = () => {
        // Sakrij "Spremljeno" dok korisnik tipka
        document.getElementById('save-status').style.opacity = '0';
        
        // Resetiraj timer
        clearTimeout(saveTimeout);
        
        // Pošalji podatke serveru nakon 1 sekunde neaktivnosti
        saveTimeout = setTimeout(submitAnswer, 1000);
    };
    
    // Slušamo 'input' događaj (svaki pritisak tipke)
    inpArt.addEventListener('input', handleInput);
    inpTit.addEventListener('input', handleInput);

    // Na Enter prebaci fokus ili spremi odmah
    inpArt.addEventListener('keypress', (e) => { if(e.key === "Enter") inpTit.focus(); });
    inpTit.addEventListener('keypress', (e) => { 
        if(e.key === "Enter") {
            submitAnswer(); 
            inpTit.blur(); // Sakrij tipkovnicu
        }
    });
});

// 2. Kraj vremena -> Zaključaj
socket.on('player_lock_input', () => {
    // Pokaži overlay preko cijelog ekrana
    document.getElementById('lock-overlay').classList.remove('d-none');
    
    // Onemogući polja fizički
    const i1 = document.getElementById('inpArtist');
    const i2 = document.getElementById('inpTitle');
    if(i1) i1.disabled = true;
    if(i2) i2.disabled = true;
    
    // Prisilno pošalji zadnje stanje (ako timer nije okinuo)
    clearTimeout(saveTimeout);
    submitAnswer();
});

// 3. Funkcija za slanje podataka serveru
function submitAnswer() {
    if (!currentSongId || !myName) return;

    const art = document.getElementById('inpArtist')?.value || "";
    const tit = document.getElementById('inpTitle')?.value || "";

    socket.emit('player_submit_answer', {
        player_name: myName,
        song_id: currentSongId,
        artist: art,
        title: tit
    });

    // Pokaži vizualnu potvrdu
    const status = document.getElementById('save-status');
    if (status) status.style.opacity = '1';
}

// --- ANTI-CHEAT ---
document.addEventListener("visibilitychange", () => {
    if(myName) {
        socket.emit('player_activity_status', {
            name: myName, 
            status: document.hidden ? 'away' : 'active'
        });
    }
});