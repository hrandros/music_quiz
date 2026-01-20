const socket = io();
const sfx = {
    correct: new Audio('/static/sfx/correct.mp3'),
    lock: new Audio('/static/sfx/lock.mp3')
};

socket.on('screen_update_status', (data) => {
    
    // Uvijek ažuriraj broj runde
    const roundText = document.getElementById('roundDisplay');
    if(roundText) roundText.innerText = `RUNDA ${data.round}`;
    
    const songText = document.getElementById('songDisplay');
    const statusLabel = document.getElementById('statusLabel');

    if (data.action === 'playing') {
        // --- OVDJE JE PROMJENA ---
        if(statusLabel) statusLabel.style.visibility = 'visible';
        
        if(songText) {
            // Ispisuje: "1. pjesma", "2. pjesma" itd.
            songText.innerText = `${data.song_index}. pjesma`;
            songText.style.color = 'white';
            songText.style.fontSize = '4rem'; // Povećaj font da se bolje vidi
        }
        
    } else {
        // Stanje čekanja
        if(statusLabel) statusLabel.style.visibility = 'hidden';
        if(songText) {
            songText.innerText = "ČEKAM...";
            songText.style.color = '#555';
            songText.style.fontSize = '3rem';
        }
    }
});

socket.on('round_locked', () => sfx.lock.play());

socket.on('screen_show_answers', d => {
    sfx.correct.play();
    const c = document.getElementById('ansKey');
    const def = document.getElementById('defIcon');
    def.classList.add('d-none'); c.classList.remove('d-none');
    c.innerHTML = "<h2 class='text-danger'>TOČNI ODGOVORI:</h2>";
    d.answers.forEach(a => {
        c.innerHTML += `<div class="fs-3 border-bottom border-secondary py-2"><span class="text-warning fw-bold">${a.artist}</span> - ${a.title}</div>`;
    });
});

socket.on('update_leaderboard', s => {
    const c = document.getElementById('lbContent');
    c.innerHTML = "";
    Object.entries(s).sort((a,b)=>b[1]-a[1]).forEach(([n, sc], i) => {
        c.innerHTML += `<div class="lb-row text-white"><span class="text-muted me-3">#${i+1}</span> ${n} <span class="float-end text-warning">${sc}</span></div>`;
    });
});