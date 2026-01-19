const socket = io();
let currentRound = 1;
let autoPlayActive = false;
let playQueue = [];
let qIdx = 0;

function selectRound(r) {
    currentRound = r;
    document.querySelectorAll('.round-tab').forEach((b,i)=>b.classList.toggle('active', i+1===r));
    document.querySelectorAll('.song-row').forEach(row => {
        row.style.display = (parseInt(row.dataset.round) === r) ? 'table-row' : 'none';
    });
    socket.emit('admin_change_round', {round: r});
}

function playSong(id) {
    const row = document.getElementById('row-'+id);
    document.getElementById('dj-console').style.display = 'block';
    if(row) {
        document.getElementById('np-artist').innerText = row.cells[2].innerText;
        row.classList.add('table-active');
    }
    socket.emit('admin_play_song', {id});
}

function stopMusic() { 
    document.getElementById('audioPlayer').pause(); 
    autoPlayActive = false;
}

function startTimer() {
    socket.emit('admin_start_timer', {sec:30});
    setTimeout(() => {
        socket.emit('admin_lock_round', {round: currentRound});
    }, 30000);
}

function toggleAutoplay() {
    autoPlayActive = !autoPlayActive;
    if(autoPlayActive) {
        playQueue = Array.from(document.querySelectorAll(`.song-row[data-round="${currentRound}"]`)).map(r => r.id.split('-')[1]);
        qIdx = 0;
        playNext();
    }
}

function playNext() {
    if(!autoPlayActive || qIdx >= playQueue.length) { startTimer(); return; }
    playSong(playQueue[qIdx]);
    
    // Ovdje bi idealno trebao znati trajanje pjesme, ali za demo čekamo 20s
    setTimeout(() => {
        if(autoPlayActive) { qIdx++; playNext(); }
    }, 20000); 
}

// Grading UI
socket.on('admin_grading_data', data => {
    document.getElementById('playlist-card').style.display = 'none';
    document.getElementById('grading-view').style.display = 'block';
    const tb = document.getElementById('gradingBody');
    tb.innerHTML = "";
    data.forEach(d => {
        tb.innerHTML += `<tr>
            <td class="text-white">${d.player}</td>
            <td><small class="text-muted">G:${d.artist_guess}<br>C:${d.c_artist}</small>
                <div class="btn-group btn-group-sm d-block mt-1">
                    <button class="btn ${d.artist_pts==1?'btn-success':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'artist_pts',1)">1</button>
                    <button class="btn ${d.artist_pts==0?'btn-danger':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'artist_pts',0)">0</button>
                </div>
            </td>
            <td><small class="text-muted">G:${d.title_guess}<br>C:${d.c_title}</small>
                <div class="btn-group btn-group-sm d-block mt-1">
                    <button class="btn ${d.title_pts==1?'btn-success':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'title_pts',1)">1</button>
                    <button class="btn ${d.title_pts==0?'btn-danger':'btn-outline-secondary'}" onclick="rate('${d.player}',${d.song_id},'title_pts',0)">0</button>
                </div>
            </td>
        </tr>`;
    });
});

function rate(p, sid, field, val) {
    let payload = {player:p, song_id:sid};
    payload[field] = val;
    socket.emit('admin_grade_answer', payload);
}

socket.on('play_audio', d => {
    const a = document.getElementById('audioPlayer');
    a.src = '/snippets/'+d.file;
    a.volume = 1;
    a.play();
});