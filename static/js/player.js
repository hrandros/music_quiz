const socket = io();
let myName="";

function joinGame() {
    const n = document.getElementById('username').value;
    const p = document.getElementById('userpin').value;
    if(n && p) socket.emit('player_join', {name:n, pin:p});
}

socket.on('join_success', d => {
    myName = d.name;
    document.getElementById('login-screen').classList.add('d-none');
    document.getElementById('game-screen').classList.remove('d-none');
    document.getElementById('player-name-display').innerText = myName;
});

socket.on('join_error', d => {
    const e = document.getElementById('login-error');
    e.classList.remove('d-none'); e.innerText = d.msg;
});

socket.on('player_round_config', d => {
    const c = document.getElementById('answer-sheet');
    c.innerHTML = `<h5 class="text-center text-secondary mb-3">RUNDA ${d.round}</h5>`;
    document.getElementById('lock-overlay').classList.add('d-none');
    
    d.songs.forEach((s, i) => {
        let inputs = "";
        if(s.type === 'standard' || s.type === 'visual') {
            inputs = `<input class="form-control mb-2 bg-black text-white" placeholder="Izvođač" onchange="sv(${s.id},'artist',this.value)">
                      <input class="form-control bg-black text-white" placeholder="Naslov" onchange="sv(${s.id},'title',this.value)">`;
        } else if(s.type === 'lyrics') {
            inputs = `<div class="text-white fst-italic mb-2">"${s.extra}"</div>
                      <input class="form-control bg-black text-white" placeholder="Riječ koja nedostaje" onchange="sv(${s.id},'artist',this.value)">`;
        }
        c.innerHTML += `<div class="card bg-dark border-secondary mb-3"><div class="card-body p-2"><div class="badge bg-secondary mb-2">#${i+1}</div>${inputs}</div></div>`;
    });
});

function sv(sid, type, val) {
    socket.emit('player_update_answer', {name:myName, song_id:sid, type, value:val, round:1}); // round treba biti dynamic
}

socket.on('round_locked', () => document.getElementById('lock-overlay').classList.remove('d-none'));
socket.on('grade_update', d => { /* Ovdje možeš dodati zelene kvačice na inpute */ });

// Anti-Cheat
document.addEventListener("visibilitychange", () => {
    if(myName) socket.emit('player_activity_status', {name:myName, status: document.hidden ? 'away' : 'active'});
});