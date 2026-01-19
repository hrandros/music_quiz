const socket = io();
const sfx = {
    correct: new Audio('/static/sfx/correct.mp3'),
    lock: new Audio('/static/sfx/lock.mp3')
};

socket.on('screen_update_status', d => {
    document.getElementById('roundDisplay').innerText = d.round;
    const img = document.getElementById('stageImg');
    const txt = document.getElementById('stageTxt');
    const def = document.getElementById('defIcon');
    const ans = document.getElementById('ansKey');
    
    img.classList.add('d-none'); txt.classList.add('d-none'); ans.classList.add('d-none'); def.classList.remove('d-none');

    if(d.type === 'visual') {
        def.classList.add('d-none'); img.classList.remove('d-none');
        img.src = '/images/'+d.image;
        img.classList.add('animate__animated','animate__zoomIn');
    }
    if(d.type === 'lyrics') {
        def.classList.add('d-none'); txt.classList.remove('d-none');
        txt.innerText = d.text;
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