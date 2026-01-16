import os
import json
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from tinytag import TinyTag 
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajna'
socketio = SocketIO(app)

# --- PUTANJE ---
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    template_folder = resource_path('templates')
    static_folder = resource_path('static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

BASE_DIR = os.getcwd()
SNIPPETS_DIR = os.path.join(BASE_DIR, 'snippets')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
# NOVO: Mapa za kvizove
QUIZZES_DIR = os.path.join(BASE_DIR, 'quizzes')
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")

os.makedirs(SNIPPETS_DIR, exist_ok=True)
os.makedirs(QUIZZES_DIR, exist_ok=True)

# --- UPRAVLJANJE MAPOM GLAZBE ---
def get_songs_dir():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get('songs_dir', os.path.join(BASE_DIR, 'songs'))
    return os.path.join(BASE_DIR, 'songs')

def save_songs_dir(path):
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    config['songs_dir'] = path
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

CURRENT_SONGS_DIR = get_songs_dir()

# --- UPRAVLJANJE AKTIVNIM KVIZOM ---
def get_active_quiz_filename():
    """Vraća ime datoteke trenutno odabranog kviza."""
    default = 'novi_kviz.json'
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get('active_quiz', default)
    return default

def set_active_quiz_filename(filename):
    """Postavlja aktivni kviz u configu."""
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    config['active_quiz'] = filename
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

def load_current_quiz():
    """Učitava podatke trenutnog kviza."""
    filename = get_active_quiz_filename()
    filepath = os.path.join(QUIZZES_DIR, filename)
    
    # Default struktura ako ne postoji
    default_data = {
        "info": {
            "title": "Novi Kviz",
            "date": datetime.date.today().strftime("%Y-%m-%d")
        },
        "songs": []
    }

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Osiguraj da ima strukturu
                if "info" not in data: data["info"] = default_data["info"]
                if "songs" not in data: data["songs"] = []
                return data
        except:
            return default_data
    return default_data

def save_current_quiz(data):
    """Sprema podatke u trenutni file."""
    filename = get_active_quiz_filename()
    filepath = os.path.join(QUIZZES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- REZANJE ---
def create_snippet(filename, start_sec, duration_sec):
    original_path = os.path.join(CURRENT_SONGS_DIR, filename)
    output_filename = f"cut_{filename}"
    output_path = os.path.join(SNIPPETS_DIR, output_filename)
    
    if os.path.exists(output_path): return output_filename
    if not os.path.exists(original_path) or not os.path.exists(FFMPEG_PATH): return None

    cmd = [FFMPEG_PATH, '-y', '-i', original_path, '-ss', str(start_sec), '-t', str(duration_sec), '-vn', '-acodec', 'libmp3lame', output_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_filename
    except: return None

# --- RUTE API ---

# 1. QUIZ MANAGER RUTE (NOVO)
@app.route('/admin/list_quizzes')
def list_quizzes():
    """Vraća popis svih kvizova u mapi quizzes."""
    quizzes = []
    active = get_active_quiz_filename()
    
    for f in os.listdir(QUIZZES_DIR):
        if f.endswith('.json'):
            path = os.path.join(QUIZZES_DIR, f)
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    info = data.get('info', {})
                    quizzes.append({
                        'filename': f,
                        'title': info.get('title', f),
                        'date': info.get('date', ''),
                        'is_active': (f == active)
                    })
            except: pass
    return jsonify(quizzes)

@app.route('/admin/create_quiz', methods=['POST'])
def create_quiz():
    """Kreira novi prazni kviz."""
    title = request.json.get('title', 'Novi Kviz')
    # Generiraj safe filename
    safe_title = "".join([c if c.isalnum() else "_" for c in title])
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    filename = f"{safe_title}_{timestamp}.json"
    
    filepath = os.path.join(QUIZZES_DIR, filename)
    data = {
        "info": {"title": title, "date": request.json.get('date')},
        "songs": []
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    set_active_quiz_filename(filename)
    return jsonify({'status': 'ok'})

@app.route('/admin/switch_quiz', methods=['POST'])
def switch_quiz():
    filename = request.json.get('filename')
    if os.path.exists(os.path.join(QUIZZES_DIR, filename)):
        set_active_quiz_filename(filename)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

@app.route('/admin/delete_quiz', methods=['POST'])
def delete_quiz():
    filename = request.json.get('filename')
    # Ne daj brisanje aktivnog ako je jedini (opcionalno)
    path = os.path.join(QUIZZES_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        # Ako smo obrisali aktivni, resetiraj na default
        if filename == get_active_quiz_filename():
             set_active_quiz_filename('novi_kviz.json')
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

# 2. PODACI O KVIZU (INFO & PJESME)
@app.route('/admin/save_quiz_info', methods=['POST'])
def save_quiz_info():
    data = load_current_quiz()
    data['info']['title'] = request.json.get('title')
    data['info']['date'] = request.json.get('date')
    save_current_quiz(data)
    return jsonify({'status': 'ok'})

@app.route('/admin/add_song', methods=['POST'])
def add_song():
    req = request.json
    data = load_current_quiz()
    new_id = 1
    if data['songs']: new_id = max(s['id'] for s in data['songs']) + 1
        
    data['songs'].append({
        "id": new_id,
        "artist": req.get('artist'), "title": req.get('title'),
        "filename": req.get('filename'),
        "start_time": int(req.get('start_time', 30)),
        "duration": int(req.get('duration', 15)),
        "round": int(req.get('round', 1))
    })
    save_current_quiz(data)
    return jsonify({'status': 'ok'})

@app.route('/admin/remove_song', methods=['POST'])
def remove_song():
    id = request.json.get('id')
    data = load_current_quiz()
    data['songs'] = [s for s in data['songs'] if s['id'] != id]
    save_current_quiz(data)
    return jsonify({'status': 'ok'})

@app.route('/admin/update_song', methods=['POST'])
def update_song():
    req = request.json
    data = load_current_quiz()
    for s in data['songs']:
        if s['id'] == req.get('id'):
            s['artist'] = req.get('artist')
            s['title'] = req.get('title')
            break
    save_current_quiz(data)
    return jsonify({'status': 'ok'})

# 3. STANDARDNE RUTE
@app.route('/admin/scan_files')
def scan_files():
    files = []
    if os.path.exists(CURRENT_SONGS_DIR):
        for f in os.listdir(CURRENT_SONGS_DIR):
            if f.lower().endswith('.mp3'):
                try:
                    tag = TinyTag.get(os.path.join(CURRENT_SONGS_DIR, f))
                    files.append({'filename': f, 'artist': tag.artist or "Nepoznato", 'title': tag.title or f})
                except: files.append({'filename': f, 'artist': "Nepoznato", 'title': f})
    return jsonify(files)

@app.route('/stream_song/<path:filename>')
def stream_song(filename): return send_from_directory(CURRENT_SONGS_DIR, filename)

@app.route('/admin/select_folder', methods=['POST'])
def select_folder():
    global CURRENT_SONGS_DIR
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    path = filedialog.askdirectory()
    root.destroy()
    if path:
        CURRENT_SONGS_DIR = path
        save_songs_dir(path)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'cancel'})

# 4. VIEW RUTE
@app.route('/')
def index(): return render_template('index.html')

@app.route('/admin/setup')
def admin_setup():
    data = load_current_quiz() # Učitaj cijeli objekt (info + songs)
    return render_template('admin_setup.html', quiz=data, current_path=CURRENT_SONGS_DIR)

@app.route('/admin/live')
def admin_live():
    data = load_current_quiz()
    return render_template('admin_live.html', songs=data['songs'])

@app.route('/player')
def player(): return render_template('player.html')

@app.route('/snippets/<filename>')
def serve_snippet(filename): return send_from_directory(SNIPPETS_DIR, filename)

@app.route('/admin/reorder_songs', methods=['POST'])
def reorder_songs():
    req = request.json
    round_num = int(req.get('round'))
    new_order_ids = req.get('order') # Lista ID-ova: [5, 2, 10...]
    
    data = load_current_quiz()
    
    # 1. Izdvoji pjesme koje NISU u ovom krugu (njih ne diramo)
    other_songs = [s for s in data['songs'] if s.get('round', 1) != round_num]
    
    # 2. Izdvoji pjesme koje JESU u ovom krugu
    current_round_songs = [s for s in data['songs'] if s.get('round', 1) == round_num]
    
    # 3. Posloži pjesme iz ovog kruga prema redoslijedu ID-ova koje smo dobili
    # Stvaramo mapu za brže pretraživanje
    song_map = {s['id']: s for s in current_round_songs}
    
    reordered_songs = []
    for song_id in new_order_ids:
        # Pazi: ID-ovi s frontenda mogu doći kao stringovi, pretvori u int
        s = song_map.get(int(song_id))
        if s:
            reordered_songs.append(s)
            
    # 4. Spoji liste (prvo ostale, pa onda ovaj krug - ili obrnuto, 
    # ali bitno je da je unutar kruga redoslijed točan)
    # Najbolje je da samo zamijenimo stari poredak novim na dnu liste
    data['songs'] = other_songs + reordered_songs
    
    save_current_quiz(data)
    return jsonify({'status': 'ok'})

# 5. SOCKETS
@socketio.on('admin_play_song')
def handle_play_song(req):
    data = load_current_quiz()
    song = next((s for s in data['songs'] if s['id'] == req['id']), None)
    if song:
        f = create_snippet(song['filename'], song['start_time'], song['duration'])
        if f: emit('play_audio', {'file': f}, broadcast=True)

@socketio.on('player_join')
def join(d): emit('admin_update_players', {'name': d['name']}, broadcast=True)

@socketio.on('player_submit_answer')
def handle_answer(data):
    # data sadrži: {'name': 'Ivan', 'answer': 'Bohemian Rhapsody'}
    print(f"ODGOVOR: {data['name']} -> {data['answer']}")
    
    # Šaljemo odgovor SAMO adminu (da drugi igrači ne vide tuđe odgovore)
    emit('admin_receive_answer', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='192.168.1.3', port=5000, debug=True)