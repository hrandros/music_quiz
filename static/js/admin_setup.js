const SETUP = {};
let wavesurfer;
document.addEventListener("DOMContentLoaded", ()=>{
    SETUP.loadFiles();
    wavesurfer = WaveSurfer.create({container:"#waveform", height:100, waveColor:"#555", progressColor:"#d00"});
});

SETUP.loadFiles = async function(){
    const res = await fetch("/admin/scan_files");
    const files = await res.json();
    const c = document.getElementById("fileList");
    c.innerHTML="";
    files.forEach(f=>{
        c.innerHTML += `<div class="d-flex justify-content-between bg-black p-2 mb-1 border-bottom border-secondary text-white small">
            <span>${f.filename}</span>
            <div>
                <button class="btn btn-xs btn-outline-info" onclick="SETUP.magic('${f.filename}')">🪄</button>
                <button class="btn btn-xs btn-success" onclick="SETUP.addToQuiz('${f.filename}','standard')">+</button>
            </div>
        </div>`;
    });
};

SETUP.magic = async function(fn){
    const res = await fetch("/admin/api_check_song", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:fn})});
    const d = await res.json();
    if(d.found && confirm(`Nađen: ${d.artist} - ${d.title}. Dodaj?`)) SETUP.addToQuiz(fn, 'standard', d.artist, d.title);
    else alert("Nije nađeno.");
};

SETUP.addToQuiz = async function(fn, type, art="", tit="", extra=""){
    await fetch("/admin/add_song_advanced", {method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({filename:fn, type, artist:art, title:tit, extra_data:extra, round:1})
    });
    location.reload();
};

SETUP.addSpecial = async function(type){
    if(type==='visual'){
        const f = document.getElementById('visualFile').files[0];
        const art = document.getElementById('visualArt').value;
        const fd = new FormData(); fd.append('file',f);
        const r = await fetch('/admin/upload_image',{method:'POST',body:fd});
        const d = await r.json();
        SETUP.addToQuiz(null, 'visual', art, 'Visual', d.filename);
    }
    if(type==='lyrics'){
        SETUP.addToQuiz(null, 'lyrics', '', 'Lyrics', document.getElementById('lyricText').value);
    }
};

SETUP.removeSong = async function(id){
    await fetch("/admin/remove_song", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id})});
    location.reload();
};