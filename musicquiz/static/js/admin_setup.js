/* static/js/admin_setup.js - NO FFMPEG VERSION */

const SETUP = {};
let wavesurfer = null;
let wsRegions = null;
let currentEditingId = null;

document.addEventListener("DOMContentLoaded", () => {
    // Inicijaliziraj WaveSurfer odmah
    try {
        SETUP.initWaveSurfer();
    } catch (e) {
        console.error("WaveSurfer init error:", e);
    }
    
    // Ako imaš API za listanje fajlova, odkomentiraj ovo
    // SETUP.loadFiles();
    
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
    // Učitaj zadnju korištenu putanju iz localStorage
    const savedPath = localStorage.getItem('rockQuiz_lastPath');
    if (savedPath) {
        const input = document.getElementById('localFolderPath');
        if (input) {
            input.value = savedPath;
            // Pozovi skeniranje odmah, ali bez blokiranja UI-a (opcionalno)
            SETUP.scanFolder(); 
        }
    }
});

// Helper za escape znakova (da navodnici ne slome HTML)
function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Pomoćna funkcija za generiranje HTML-a reda tablice
function addSongToTableHTML(s) {
    const tbody = document.getElementById('quizSongsList');
    if (!tbody) {
        location.reload(); // Ako ne nađe tablicu, reload je najsigurniji
        return;
    }

    const tr = document.createElement('tr');
    tr.className = 'q-row';
    tr.id = 'qrow-' + s.id;
    tr.setAttribute('data-round', s.round);
    tr.setAttribute('data-id', s.id);

    // Provjera trenutnog filtera runde da ne dodamo vidljivu pjesmu u krivu rundu
    const activeFilterBtn = document.querySelector('.round-filter.active');
    if (activeFilterBtn) {
        const currentFilter = parseInt(activeFilterBtn.dataset.round);
        if (currentFilter !== 0 && currentFilter != s.round) {
            tr.style.display = 'none';
        }
    }

    tr.innerHTML = `
        <td class="ps-3" style="width:40px;">
            <span class="badge bg-warning text-dark">R${s.round}</span>
        </td>
        <td>
            <div class="fw-bold text-white text-truncate" style="max-width: 250px;">${s.artist}</div>
            <div class="small text-muted text-truncate" style="max-width: 250px;">${s.title}</div>
        </td>
        <td class="text-end pe-3" style="width:100px;">
            <div class="btn-group">
                <button class="btn btn-sm btn-outline-info" onclick="SETUP.openEditor('${s.id}', '${s.filename}', '${s.artist}', '${s.title}', '${s.start}', '${s.duration}')">
                    <i class="bi bi-pencil-fill"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="SETUP.removeSong('${s.id}')">
                    <i class="bi bi-trash-fill"></i>
                </button>
            </div>
        </td>
    `;
    tbody.appendChild(tr);
}


// --- WAVESURFER INIT ---
SETUP.initWaveSurfer = function() {
    if(typeof WaveSurfer === 'undefined') return;
    
    if (wavesurfer) {
        wavesurfer.destroy();
        wavesurfer = null;
    }

    wavesurfer = WaveSurfer.create({
        container: "#waveform",
        waveColor: '#666',
        progressColor: '#d32f2f',
        cursorColor: '#fff',
        height: 100,
        normalize: true,
        // Bitno: MediaElement backend je bolji za velike fajlove
        backend: 'MediaElement'
    });

    // Prikaz trenutnog vremena
    wavesurfer.on('timeupdate', (currentTime) => {
        const lbl = document.getElementById('lblCurrent');
        if(lbl) lbl.innerText = currentTime.toFixed(1) + 's';
    });
    
    // Ikone play/pause
    wavesurfer.on('play', () => { 
        const i = document.querySelector('#btnPlayPause i');
        if(i) i.className = 'bi bi-pause-fill'; 
    });
    wavesurfer.on('pause', () => { 
        const i = document.querySelector('#btnPlayPause i');
        if(i) i.className = 'bi bi-play-fill'; 
    });

    // Kontrola glasnoće
    const volSlider = document.getElementById('wsVolume');
    if(volSlider) {
        wavesurfer.setVolume(volSlider.value);
        volSlider.oninput = function() {
            wavesurfer.setVolume(this.value);
        };
    }

    // Regions plugin (za odabir start/end vremena)
    if (window.WaveSurfer.Regions) {
        wsRegions = wavesurfer.registerPlugin(window.WaveSurfer.Regions.create());
        
        wsRegions.on('region-updated', (region) => {
            const s = document.getElementById('lblStart');
            const d = document.getElementById('lblDur');
            if(s) s.innerText = region.start.toFixed(1);
            if(d) d.innerText = (region.end - region.start).toFixed(1);
        });
        
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

    if (!wavesurfer) SETUP.initWaveSurfer();

    currentEditingId = id;
    
    // UI Prikaz
    const panel = document.getElementById('editorPanel');
    if(panel) panel.style.display = 'block';
    
    document.getElementById('editId').value = id;
    document.getElementById('editArtist').value = artist;
    document.getElementById('editTitle').value = title;
    
    // Označi red u tablici
    document.querySelectorAll('.q-row').forEach(r => r.classList.remove('editing-row'));
    const row = document.getElementById('qrow-'+id);
    if(row) row.classList.add('editing-row');

    // Učitaj audio: Koristimo rutu /stream_song/ + filename
    wavesurfer.load('/stream_song/' + filename);
    
    wavesurfer.once('ready', () => {
        if(wsRegions) {
            wsRegions.clearRegions();
            // Kreiraj regiju na temelju spremljenih podataka
            wsRegions.addRegion({
                start: parseFloat(start),
                end: parseFloat(start) + parseFloat(dur),
                color: "rgba(211, 47, 47, 0.4)",
                drag: true,
                resize: true
            });
            // Skoči na početak regije
            wavesurfer.setTime(parseFloat(start));
        }
    });
    
    wavesurfer.once('error', (e) => {
        console.error("WaveSurfer error:", e);
        alert("Ne mogu učitati pjesmu: " + filename);
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

    // Pozivamo API za update (ako ga nemaš u pythonu, moraš ga dodati!)
    // Pretpostavljam da koristiš /admin/add_song_advanced ili slično za update, 
    // ili trebaš dodati novu rutu /admin/update_song u python.
    
    // Ovdje pretpostavljam da ruta za update postoji (ako ne, javi da dodamo u python)
    const res = await fetch("/admin/update_song", { // <--- PAZI: Imaš li ovu rutu u pythonu?
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            id: currentEditingId,
            artist: artist,
            title: title,
            start: start,
            duration: duration
        })
    });
    
    // Ako nemaš update rutu, možeš koristiti remove pa add, ali to mijenja ID.
    // Najbolje je dodati rutu u python.
    
    try {
        const data = await res.json();
        if(data.status === 'ok') location.reload();
        else alert("Greška pri spremanju!");
    } catch(e) {
        alert("Greška: Provjeri postoji li ruta /admin/update_song u pythonu.");
    }
};

// --- UPRAVLJANJE PJESMAMA ---

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
    if(!t) return alert("Upiši naziv!");
    await fetch("/admin/create_quiz", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ title: t })
    });
    location.reload();
};

SETUP.filterView = function(round, btn) {
    document.querySelectorAll('.btn-group .btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.q-row').forEach(row => {
        row.style.display = (round === 0 || parseInt(row.dataset.round) === round) ? 'table-row' : 'none';
    });
};

SETUP.scanFolder = async function() {
    const pathInput = document.getElementById('localFolderPath');
    const path = pathInput.value.trim();
    const listContainer = document.getElementById('repoFileList');
    
    if(!path) {
        alert("Molimo unesite putanju do mape!");
        return;
    }

    localStorage.setItem('rockQuiz_lastPath', path);

    listContainer.innerHTML = '<div class="text-white text-center p-2"><div class="spinner-border spinner-border-sm"></div> Tražim...</div>';

    try {
        const res = await fetch("/admin/scan_local_folder", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        
        if(data.status === 'error') {
            listContainer.innerHTML = `<div class="text-danger p-2 small">${data.msg}</div>`;
            return;
        }

        if(data.files.length === 0) {
            listContainer.innerHTML = `<div class="text-warning p-2 small">Nema MP3 datoteka u ovoj mapi.</div>`;
            return;
        }

        // Renderiraj listu
        let html = '';
        data.files.forEach(f => {
            // Putanja + ime fajla (pazimo na slash/backslash ovisno o OS-u, ali za import šaljemo oboje)
            // Koristimo path iz inputa kao base
            const fullPath = path.endsWith('\\') || path.endsWith('/') ? path + f : path + '/' + f;
            
            // --- NOVO: Izdvajanje samo imena datoteke za ljepši prikaz ---
            // Dijelimo po '/' (jer nam backend šalje relativne putanje s forward slashom)
            const fileNameWithExt = f.split('/').pop();
            
            html += `
            <div class="d-flex justify-content-between align-items-center bg-black p-2 mb-1 border-bottom border-secondary text-white">
                <div class="me-2 overflow-hidden" style="min-width: 0;">
                    <div class="fw-bold text-truncate" style="font-size: 0.95rem;">${fileNameWithExt.replace(/\.mp3$/i, '')}</div>
                    <div class="text-muted text-truncate" style="font-size: 0.7rem;"><i class="bi bi-folder2 me-1"></i>${f}</div>
                </div>
                <div class="flex-shrink-0">
                    <button class="btn btn-sm btn-outline-info me-1" 
                        onclick="SETUP.magicCheck('${fullPath.replace(/\\/g, '\\\\')}', '${fileNameWithExt.replace(/'/g, "\\'")}')">
                        <i class="bi bi-magic"></i>
                    </button>
                    <button class="btn btn-sm btn-success" 
                        onclick="SETUP.importSong('${fullPath.replace(/\\/g, '\\\\')}', '${f.replace(/'/g, "\\'")}')">
                        <i class="bi bi-plus-lg"></i>
                    </button>
                </div>
            </div>`;
        });
        listContainer.innerHTML = html;

    } catch(e) {
        console.error(e);
        listContainer.innerHTML = `<div class="text-danger p-2 small">Greška pri skeniranju.</div>`;
    }
};

// Ažurirana funkcija koja prima i metapodatke
SETUP.importSong = async function(fullPath, filename, artist = "", title = "") {
    const r = document.getElementById('targetRound') ? document.getElementById('targetRound').value : 1;
    
    // Vizualni feedback na gumbu
    // Koristimo event.currentTarget ako je kliknuto, ili tražimo gumb po putanji
    const btn = event ? event.currentTarget : null;
    const originalContent = btn ? btn.innerHTML : "";
    
    if(btn && btn.disabled) return; 
    
    if(btn) {
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        btn.disabled = true;
    }

    try {
        const res = await fetch("/admin/import_external_song", {
            method: "POST", 
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ 
                source_path: fullPath,
                filename: filename,
                round: r,
                artist: artist, // Šaljemo izvođača ako postoji
                title: title    // Šaljemo naslov ako postoji
            })
        });
        const data = await res.json();
        
        if(data.status === 'ok') {
            if(btn) {
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-success');
                btn.innerHTML = '<i class="bi bi-check-lg"></i>';
            }
            
            // Dodaj pjesmu u tablicu desno
            addSongToTableHTML(data.song);
            
            const emptyMsg = document.querySelector('.table-container .text-center');
            if(emptyMsg) emptyMsg.style.display = 'none';

        } else {
            alert("Greška: " + data.msg);
            if(btn) {
                btn.innerHTML = originalContent;
                btn.disabled = false;
            }
        }
    } catch(e) {
        console.error(e);
        if(btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    }
};

SETUP.openPicker = async function() {
    const btn = event.currentTarget;
    const oldIcon = btn.innerHTML;
    
    // Vizualni feedback da se nešto događa
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;

    try {
        // Pozovi Python da otvori prozor
        const res = await fetch("/admin/open_folder_picker");
        const data = await res.json();
        
        if(data.status === 'ok' && data.path) {
            // Upiši putanju u input polje
            document.getElementById('localFolderPath').value = data.path;
            // Spremi putanju u local storage
            localStorage.setItem('rockQuiz_lastPath', data.path);
            // Automatski pokreni skeniranje
            SETUP.scanFolder();
        }
    } catch(e) {
        console.error("Greška pri otvaranju pickera:", e);
    }

    // Vrati gumb u normalu
    btn.innerHTML = oldIcon;
    btn.disabled = false;
};

SETUP.magicCheck = async function(fullPath, filename) {
    const btn = event.currentTarget;
    const oldHtml = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;

    try {
        const res = await fetch("/admin/api_check_deezer", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ filename: filename }) 
        });
        const data = await res.json();

        if (data.status === "ok" && data.found) {
            if (confirm(`Pronađeno:\n\nIzvođač: ${data.artist}\nNaslov: ${data.title}\n\nUvesti s ovim podacima?`)) {
                await SETUP.importSong(fullPath, filename, data.artist, data.title);
            }
        } else {
            alert("Deezer nije pronašao podatke za: " + filename);
        }
    } catch (e) {
        console.error(e);
        alert("Greška u komunikaciji s Deezerom.");
    } finally {
        btn.innerHTML = oldHtml;
        btn.disabled = false;
    }
};