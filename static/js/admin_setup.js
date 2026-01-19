const SETUP = {};

document.addEventListener("DOMContentLoaded", () => {
    SETUP.loadFiles();
});

// --- LOAD FILES (MP3) ---
SETUP.loadFiles = async function () {
    const res = await fetch("/admin/scan_files");
    const files = await res.json();
    const c = document.getElementById("fileList");
    if (!c) return;
    
    c.innerHTML = "";
    files.forEach(f => {
        // Klik na pjesmu je selektira (da znamo koja je odabrana za mashup)
        c.innerHTML += `
        <div class="d-flex justify-content-between bg-black p-2 mb-1 border-bottom border-secondary text-white small song-item" 
             onclick="selectFile(this, '${f.filename}')">
            <span>${f.filename}</span>
            <div>
                <button class="btn btn-xs btn-outline-info" onclick="event.stopPropagation(); SETUP.magic('${f.filename}')" title="Auto-Detect">🪄</button>
                <button class="btn btn-xs btn-success" onclick="event.stopPropagation(); SETUP.addToQuiz('${f.filename}','standard')">
                    <i class="bi bi-plus-lg"></i>
                </button>
            </div>
        </div>`;
    });
};

// Pomoćna za selektiranje u listi
let selectedFilename = null;
window.selectFile = function(el, fn) {
    document.querySelectorAll('.song-item').forEach(e => e.classList.remove('bg-primary'));
    el.classList.add('bg-primary');
    selectedFilename = fn;
}

// --- DEEZER MAGIC ---
SETUP.magic = async function (fn) {
    const res = await fetch("/admin/api_check_song", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: fn })
    });
    const d = await res.json();
    if (d.found && confirm(`Nađen: ${d.artist} - ${d.title}.\nDodati u trenutno odabranu rundu?`)) {
        SETUP.addToQuiz(fn, 'standard', d.artist, d.title);
    } else if (!d.found) {
        alert("Nije pronađeno.");
    }
};

// --- CORE: ADD TO QUIZ ---
SETUP.addToQuiz = async function (fn, type, art = "", tit = "", extra = "") {
    // Čitamo odabranu rundu iz dropdowna
    const r = document.getElementById('targetRound').value;
    
    if (!fn && type === 'standard') return alert("Greška: Nema filename-a");

    await fetch("/admin/add_song_advanced", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            filename: fn,
            type: type,
            artist: art,
            title: tit,
            extra_data: extra,
            round: r // Šaljemo odabranu rundu
        })
    });
    location.reload();
};

// --- SPECIAL TYPES ---
SETUP.addSpecial = async function (type) {
    // Uvijek čitamo odabranu rundu
    const r = document.getElementById('targetRound').value;

    if (type === 'visual') {
        const f = document.getElementById('visualFile').files[0];
        const art = document.getElementById('visualArt').value;
        if (!f) return alert("Odaberi sliku!");

        const fd = new FormData(); fd.append('file', f);
        const res = await fetch('/admin/upload_image', { method: 'POST', body: fd });
        const data = await res.json();

        // Visual nema mp3 (filename=null), image_file=data.filename
        // Pozivamo backend ručno jer addToQuiz funkcija gore očekuje strukturu za standard
        await fetch("/admin/add_song_advanced", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: 'visual',
                image_file: data.filename,
                artist: art,
                title: 'Visual Round',
                round: r
            })
        });
        location.reload();
    }
    
    if (type === 'lyrics') {
        const txt = document.getElementById('lyricText').value;
        if(!txt) return alert("Upiši tekst!");
        SETUP.addToQuiz(null, 'lyrics', '', 'Lyrics Challenge', txt);
    }

    if (type === 'mashup') {
        if(!selectedFilename) return alert("Prvo klikni na MP3 pjesmu u Audio listi lijevo!");
        const a1 = document.getElementById('msh1').value;
        const a2 = document.getElementById('msh2').value;
        SETUP.addToQuiz(selectedFilename, 'mashup', a1, 'Mashup', a2);
    }
};

// --- REMOVE SONG ---
SETUP.removeSong = async function (id) {
    if(!confirm("Obrisati?")) return;
    await fetch("/admin/remove_song", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
    });
    location.reload();
};

// --- CREATE NEW QUIZ (MODAL) ---
SETUP.createNewQuiz = async function () {
    const title = document.getElementById('newQuizTitle').value;
    const date = document.getElementById('newQuizDate').value;

    if (!title) return alert("Upiši naziv kviza!");

    await fetch("/admin/create_quiz", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, date })
    });

    location.reload();
};

// --- FILTER VIEW (R1, R2...) ---
SETUP.filterView = function(round, btn) {
    // Vizualno
    document.querySelectorAll('.btn-group .btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const rows = document.querySelectorAll('.q-row');
    rows.forEach(row => {
        if (round === 0) {
            row.style.display = 'table-row';
        } else {
            row.style.display = (parseInt(row.dataset.round) === round) ? 'table-row' : 'none';
        }
    });
}