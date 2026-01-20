/* static/js/admin_setup.js - FIXED WAVESURFER V7 */

const SETUP = {};
let wavesurfer = null;
let wsRegions = null;
let currentEditingId = null;

document.addEventListener("DOMContentLoaded", () => {
    // Pokušaj inicijalizirati odmah
    try {
        SETUP.initWaveSurfer();
    } catch (e) {
        console.error("WaveSurfer init error:", e);
    }
    
    SETUP.loadFiles();
    
    // Sortable Init (Drag & Drop)
    const el = document.getElementById('quizSongsList');
    if (el && typeof Sortable !== 'undefined') {
        Sortable.create(el, {
            animation: 150,
            handle: '.q-row',
            onEnd: function (evt) {
                // Ovdje bi išao reorder API poziv
            }
        });
    }
});

// --- WAVESURFER INIT (AŽURIRANO: Time & Volume) ---
SETUP.initWaveSurfer = function() {
    if(typeof WaveSurfer === 'undefined') return;
    
    // Uništi stari ako postoji
    if (wavesurfer) {
        wavesurfer.destroy();
        wavesurfer = null;
    }

    // Kreiraj instancu
    wavesurfer = WaveSurfer.create({
        container: "#waveform",
        waveColor: '#666',
        progressColor: '#d32f2f',
        cursorColor: '#fff',
        height: 100,
        normalize: true,
        backend: 'MediaElement'
    });

    // --- 1. AŽURIRANJE TRENUTNOG VREMENA ---
    wavesurfer.on('timeupdate', (currentTime) => {
        const lbl = document.getElementById('lblCurrent');
        if(lbl) lbl.innerText = currentTime.toFixed(1) + 's';
    });
    
    // Promjena ikone play/pause kad završi ili pauzira
    wavesurfer.on('play', () => { document.querySelector('#btnPlayPause i').className = 'bi bi-pause-fill'; });
    wavesurfer.on('pause', () => { document.querySelector('#btnPlayPause i').className = 'bi bi-play-fill'; });

    // --- 2. KONTROLA GLASNOĆE ---
    const volSlider = document.getElementById('wsVolume');
    if(volSlider) {
        // Postavi početnu glasnoću na max (ili koliko je slider)
        wavesurfer.setVolume(volSlider.value);
        
        // Slušaj promjene
        volSlider.oninput = function() {
            wavesurfer.setVolume(this.value);
        };
    }

    // Dodaj Regions plugin
    if (window.WaveSurfer.Regions) {
        wsRegions = wavesurfer.registerPlugin(window.WaveSurfer.Regions.create());
        
        wsRegions.on('region-updated', (region) => {
            const s = document.getElementById('lblStart');
            const d = document.getElementById('lblDur');
            if(s) s.innerText = region.start.toFixed(1);
            if(d) d.innerText = (region.end - region.start).toFixed(1);
        });
        
        // Kad klikneš na regiju, postavi vrijeme playera na početak regije
        wsRegions.on('region-clicked', (region, e) => {
            e.stopPropagation();
            region.play();
        });
    }

    // Play/Pause gumb
    const btn = document.getElementById('btnPlayPause');
    if(btn) btn.onclick = () => wavesurfer.playPause();
};

// --- OTVORI EDITOR ---
SETUP.openEditor = function(id, filename, artist, title, start, dur) {
    if (!filename || filename === 'None') {
        alert("Ovo nije audio pitanje (nema MP3).");
        return;
    }

    // SIGURNOSNA PROVJERA: Je li wavesurfer živ?
    if (!wavesurfer) {
        console.log("WaveSurfer nije aktivan, pokušavam ponovno inicijalizirati...");
        SETUP.initWaveSurfer();
        
        // Ako i dalje ne radi (npr. skripta se nije učitala s interneta)
        if (!wavesurfer) {
            alert("Greška: WaveSurfer biblioteka nije učitana. Provjeri internet vezu i osvježi stranicu.");
            return;
        }
    }

    currentEditingId = id;
    
    // UI
    const panel = document.getElementById('editorPanel');
    if(panel) panel.style.display = 'block';
    
    document.getElementById('editId').value = id;
    document.getElementById('editArtist').value = artist;
    document.getElementById('editTitle').value = title;
    
    // Označi red
    document.querySelectorAll('.q-row').forEach(r => r.classList.remove('editing-row'));
    const row = document.getElementById('qrow-'+id);
    if(row) row.classList.add('editing-row');

    // Učitaj audio
    // Dodajemo timestamp da izbjegnemo browser cache ako se fajl promijenio
    wavesurfer.load('/stream_song/' + filename + '?t=' + new Date().getTime());
    
    // Postavi regiju kad je spreman
    wavesurfer.once('ready', () => {
        if(wsRegions) {
            wsRegions.clearRegions();
            wsRegions.addRegion({
                start: start,
                end: start + dur,
                color: "rgba(211, 47, 47, 0.4)",
                drag: true,
                resize: true
            });
        }
    });
    
    // Error handling za load
    wavesurfer.once('error', (e) => {
        console.error("WaveSurfer error:", e);
        alert("Ne mogu učitati pjesmu. Provjeri je li datoteka u mapi 'songs'.");
    });
};

SETUP.closeEditor = function() {
    const panel = document.getElementById('editorPanel');
    if(panel) panel.style.display = 'none';
    if(wavesurfer) wavesurfer.pause();
    document.querySelectorAll('.q-row').forEach(r => r.classList.remove('editing-row'));
};

SETUP.saveChanges = async function() {
    if(!currentEditingId) return;
    
    const artist = document.getElementById('editArtist').value;
    const title = document.getElementById('editTitle').value;
    
    let start = 0, duration = 15;
    if (wsRegions) {
        const regions = wsRegions.getRegions();
        if (regions.length > 0) {
            start = regions[0].start;
            duration = regions[0].end - regions[0].start;
        }
    }

    const res = await fetch("/admin/update_song", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            id: currentEditingId,
            artist: artist,
            title: title,
            start: start,
            duration: duration
        })
    });
    
    const data = await res.json();
    if(data.status === 'ok') location.reload();
    else alert("Greška pri spremanju!");
};


// --- OSTALE FUNKCIJE ---

SETUP.loadFiles = async function() {
    const res = await fetch("/admin/scan_files");
    const files = await res.json();
    const c = document.getElementById("fileList");
    if(!c) return;

    c.innerHTML = "";
    files.forEach(f => {
        c.innerHTML += `
        <div class="d-flex justify-content-between bg-black p-2 mb-1 border-bottom border-secondary text-white small song-item" 
             onclick="selectFile(this, '${f.filename}')">
            <span class="text-truncate" style="max-width:200px;" title="${f.filename}">${f.filename}</span>
            <div>
                <button class="btn btn-xs btn-outline-info me-1" onclick="event.stopPropagation(); SETUP.magic('${f.filename}')">🪄</button>
                <button class="btn btn-xs btn-success" onclick="event.stopPropagation(); SETUP.addToQuiz('${f.filename}','standard')">+</button>
            </div>
        </div>`;
    });
};

// Selektiranje za mashup
let selectedFilename = null;
window.selectFile = function(el, fn) {
    document.querySelectorAll('.song-item').forEach(e => e.classList.remove('bg-primary'));
    el.classList.add('bg-primary');
    selectedFilename = fn;
}

SETUP.magic = async function (fn) {
    const btn = event.currentTarget; // Visual feedback
    const oldHtml = btn.innerHTML;
    btn.innerHTML = "⌛";
    
    try {
        const res = await fetch("/admin/api_check_song", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: fn })
        });
        const d = await res.json();
        if (d.found && confirm(`Nađen: ${d.artist} - ${d.title}.\nDodati?`)) {
            SETUP.addToQuiz(fn, 'standard', d.artist, d.title);
        } else if (!d.found) alert("Nije pronađeno.");
    } catch(e) { console.error(e); }
    
    btn.innerHTML = oldHtml;
};

SETUP.addToQuiz = async function (fn, type, art = "", tit = "", extra = "") {
    const r = document.getElementById('targetRound') ? document.getElementById('targetRound').value : 1;
    await fetch("/admin/add_song_advanced", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: fn, type, artist: art, title: tit, extra_data: extra, round: r })
    });
    location.reload();
};

SETUP.addSpecial = async function (type) {
    const r = document.getElementById('targetRound').value;

    if (type === 'visual') {
        const f = document.getElementById('visualFile').files[0];
        const art = document.getElementById('visualArt').value;
        if (!f) return alert("Odaberi sliku!");

        const fd = new FormData(); fd.append('file', f);
        const res = await fetch('/admin/upload_image', { method: 'POST', body: fd });
        const data = await res.json();

        await fetch("/admin/add_song_advanced", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: 'visual', image_file: data.filename, artist: art, title: 'Visual Round', round: r })
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
        // Za mashup koristimo selectedFilename
        SETUP.addToQuiz(selectedFilename, 'mashup', a1, 'Mashup', a2);
    }
};

SETUP.removeSong = async function (id) {
    if(!confirm("Obrisati?")) return;
    await fetch("/admin/remove_song", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
    });
    location.reload();
};

SETUP.createNewQuiz = async function () {
    const t = document.getElementById('newQuizTitle').value;
    const d = document.getElementById('newQuizDate').value;
    if(!t) return alert("Upiši naziv!");
    await fetch("/admin/create_quiz", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ title: t, date: d })
    });
    location.reload();
};

SETUP.switchQuiz = async function(id) {
    if(id == 0) return;
    
    // Pokaži loading (opcionalno)
    document.getElementById('quizSwitcher').disabled = true;

    await fetch("/admin/switch_quiz", {
        method: "POST", 
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
    });
    
    // Osvježi stranicu da se učitaju pjesme tog kviza
    location.reload();
};

SETUP.filterView = function(round, btn) {
    document.querySelectorAll('.btn-group .btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.q-row').forEach(row => {
        row.style.display = (round === 0 || parseInt(row.dataset.round) === round) ? 'table-row' : 'none';
    });
};