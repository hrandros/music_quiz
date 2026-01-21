import os
import sys
import datetime
import socket
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from difflib import SequenceMatcher
from werkzeug.utils import secure_filename
import shutil
import tkinter as tk
from tkinter import filedialog

# --- CONFIG ---
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    template_folder = resource_path('templates')
    static_folder = resource_path('static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.config['SECRET_KEY'] = 'rocknroll2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kviz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

ADMIN_PASSWORD = "admin"
BASE_DIR = os.getcwd()
DEFAULT_SONGS_DIR = os.path.join(BASE_DIR, 'songs')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
live_player_status = {}

os.makedirs(DEFAULT_SONGS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- DATABASE MODELS ---
class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.String(20), default=datetime.date.today().strftime("%Y-%m-%d"))
    is_active = db.Column(db.Boolean, default=False)

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    type = db.Column(db.String(20), default="standard") 
    filename = db.Column(db.String(300), nullable=True)
    image_file = db.Column(db.String(300), nullable=True)
    artist = db.Column(db.String(100), default="?")
    title = db.Column(db.String(100), default="?")
    extra_data = db.Column(db.String(500), default="") 
    start_time = db.Column(db.Float, default=0.0)
    duration = db.Column(db.Float, default=15.0)
    round_number = db.Column(db.Integer, default=1)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    pin = db.Column(db.String(4), nullable=False)
    score = db.Column(db.Float, default=0.0)
    last_active = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100))
    round_number = db.Column(db.Integer)
    song_id = db.Column(db.Integer)
    artist_guess = db.Column(db.String(200), default="")
    title_guess = db.Column(db.String(200), default="")
    extra_guess = db.Column(db.String(200), default="")
    artist_points = db.Column(db.Float, default=0.0)
    title_points = db.Column(db.Float, default=0.0)
    extra_points = db.Column(db.Float, default=0.0)
    is_locked = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

# --- HELPERS ---
def get_active_quiz(): return Quiz.query.filter_by(is_active=True).first()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'): return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def calculate_similarity(u, c):
    if not u or not c: return 0.0
    u, c = u.strip().lower(), c.strip().lower()
    if u == c: return 1.0
    return 1.0 if SequenceMatcher(None, u, c).ratio() >= 0.85 else 0.0

def get_all_players_data():
    players = Player.query.all()
    data = []
    for p in players:
        data.append({
            "name": p.name,
            "score": p.score,
            "status": live_player_status.get(p.name, 'offline') # active, away, offline
        })
    return data

# --- ROUTES ---
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_live'))
        flash('Kriva lozinka!', 'danger')
    return render_template('login.html')

@app.route("/")
def index(): return render_template("index.html")

@app.route("/player")
def player(): return render_template("player.html")

@app.route('/screen')
def screen(): 
    q = get_active_quiz()
    return render_template('screen.html', quiz={"info":{"title":q.title if q else "","date":""}})

@app.route("/admin/live")
@login_required
def admin_live():
    q = get_active_quiz()
    songs = Song.query.filter_by(quiz_id=q.id).order_by(Song.id).all() if q else []
    return render_template("admin_live.html", songs=songs, quiz=q)

@app.route("/admin/setup")
@login_required
def admin_setup():
    q = get_active_quiz()
    all_q = Quiz.query.all()
    songs = Song.query.filter_by(quiz_id=q.id).order_by(Song.id).all() if q else []
    return render_template("admin_setup.html", quiz=q, all_quizzes=all_q, songs=songs)

@app.route('/images/<filename>')
def serve_image(filename): return send_from_directory(IMAGES_DIR, filename)

@app.route('/stream_song/<path:filename>')
def stream_song(filename): return send_from_directory(DEFAULT_SONGS_DIR, filename)

# --- API ---
@app.route("/admin/create_quiz", methods=["POST"])
@login_required
def create_quiz():
    # Deaktiviraj sve stare
    Quiz.query.update({Quiz.is_active: False})
    
    # Kreiraj novi i postavi ga kao aktivnog
    new_quiz = Quiz(title=request.json.get("title"), is_active=True)
    db.session.add(new_quiz)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/admin/open_folder_picker", methods=["GET"])
@login_required
def open_folder_picker():
    """Otvara Windows prozor za odabir mape i vraća putanju."""
    try:
        # Kreiraj skriveni root prozor jer ne želimo cijelu GUI aplikaciju
        root = tk.Tk()
        root.withdraw() 
        root.attributes('-topmost', True) # Prisili prozor da dođe u prvi plan
        
        # Otvori dijalog
        path = filedialog.askdirectory(title="Odaberi mapu s glazbom")
        
        root.destroy() # Ubij prozor nakon odabira
        
        if path:
            # Normaliziraj putanju (pretvori \ u / da radi ljepše)
            path = path.replace('\\', '/')
            return jsonify({"status": "ok", "path": path})
        else:
            return jsonify({"status": "cancel"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route("/admin/scan_local_folder", methods=["POST"])
@login_required
def scan_local_folder():
    raw_path = request.json.get("path")
    if not raw_path:
        return jsonify({"status": "error", "msg": "Putanja nije definirana."})
    
    # Popravak putanje za Windows (miče navodnike ako ih je netko kopirao)
    folder_path = raw_path.strip('"').strip("'")
    
    if not os.path.isdir(folder_path):
        return jsonify({"status": "error", "msg": "Mapa ne postoji."})
    
    mp3_files = []
    try:
        # Listaj datoteke
        for f in os.listdir(folder_path):
            # Provjera ekstenzije (case-insensitive, hvata mp3 i MP3)
            if f.lower().endswith('.mp3'):
                mp3_files.append(f)
        
        return jsonify({"status": "ok", "files": mp3_files})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route("/admin/import_external_song", methods=["POST"])
@login_required
def import_external_song():
    try:
        data = request.json
        source_path = data.get("source_path")
        filename = data.get("filename")
        
        # Provjera aktivnog kviza
        q = get_active_quiz()
        if not q:
            return jsonify({"status": "error", "msg": "Nema aktivnog kviza! Kreiraj ili odaberi kviz."})

        if not os.path.exists(source_path):
            return jsonify({"status": "error", "msg": "Izvorna datoteka ne postoji."})

        # Sigurnosna kopija imena da izbjegnemo duplikate
        safe_filename = secure_filename(filename)
        destination = os.path.join(DEFAULT_SONGS_DIR, safe_filename)
        
        # Kopiraj datoteku
        shutil.copy2(source_path, destination)

        # Dodaj u bazu
        s = Song(
            quiz_id=q.id,
            filename=safe_filename,
            artist="Nepoznato",     # Default, promijeniš u editoru
            title=safe_filename.replace(".mp3", ""),
            start_time=0.0,
            duration=15.0,
            round_number=int(data.get("round", 1))
        )
        db.session.add(s)
        db.session.commit()

        # VRATI PODATKE O PJESMI (Bitno za frontend!)
        song_data = {
            "id": s.id,
            "artist": s.artist,
            "title": s.title,
            "filename": s.filename,
            "start": s.start_time,
            "duration": s.duration,
            "round": s.round_number
        }

        return jsonify({"status": "ok", "song": song_data})
        
    except Exception as e:
        print("ERROR IMPORTING:", e) # Ispis greške u konzolu
        return jsonify({"status": "error", "msg": str(e)})

@app.route("/admin/add_song_advanced", methods=["POST"])
@login_required
def add_song_advanced():
    q = get_active_quiz()
    d = request.json
    s = Song(quiz_id=q.id, type=d.get("type"), filename=d.get("filename"), image_file=d.get("image_file"),
             artist=d.get("artist"), title=d.get("title"), extra_data=d.get("extra_data"),
             start_time=float(d.get("start_time",0)), duration=float(d.get("duration",15)), round_number=int(d.get("round",1)))
    db.session.add(s)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/admin/remove_song", methods=["POST"])
@login_required
def remove_song():
    Song.query.filter_by(id=request.json.get("id")).delete()
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/admin/update_song", methods=["POST"])
@login_required
def update_song():
    data = request.json
    song = Song.query.get(data.get("id"))
    if song:
        song.artist = data.get("artist")
        song.title = data.get("title")
        song.start_time = float(data.get("start"))
        song.duration = float(data.get("duration"))
        db.session.commit()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "msg": "Song not found"}), 404

# --- SOCKETS ---
@socketio.on("player_join")
def handle_join(d):
    p = Player.query.filter_by(name=d["name"]).first()
    if not p:
        p = Player(name=d["name"], pin=d.get("pin","0000"))
        db.session.add(p)
    elif p.pin != d.get("pin"):
        emit("join_error", {"msg": "Krivi PIN!"}, to=request.sid); return
    
    db.session.commit()
    
    # NOVO: Zabilježi da je igrač aktivan
    live_player_status[p.name] = 'active'
    
    # Spoji ga u "sobu" s njegovim imenom (za privatne poruke/lock)
    from flask_socketio import join_room
    join_room(d["name"]) 
    
    emit("join_success", {"name": p.name}, to=request.sid)
    
    # Javi adminu da osvježi listu
    emit("admin_update_player_list", get_all_players_data(), broadcast=True)

@socketio.on("player_activity_status")
def handle_activity(data):
    # Igrač šalje: {name: "Tim1", status: "away"}
    name = data.get('name')
    status = data.get('status')
    live_player_status[name] = status
    
    # Javi adminu odmah
    emit("admin_single_player_update", {"name": name, "status": status}, broadcast=True)

# NOVO: Admin traži listu svih igrača (kad otvori stranicu)
@socketio.on("admin_get_players")
def handle_get_players():
    emit("admin_player_list_full", get_all_players_data())

# NOVO: Admin zaključava pojedinog igrača
@socketio.on("admin_lock_single_player")
def handle_single_lock(data):
    player_name = data.get('player_name')
    song_id = data.get('song_id')
    
    # 1. Nađi ili kreiraj odgovor i zaključaj ga u bazi
    ans = Answer.query.filter_by(player_name=player_name, song_id=song_id).first()
    if not ans:
        # Ako odgovor još ne postoji, kreiraj prazan i zaključan
        # Moramo znati rundu, pretpostavimo da je aktivna pjesma
        song = Song.query.get(song_id)
        if song:
            ans = Answer(player_name=player_name, song_id=song_id, round_number=song.round_number, is_locked=True)
            db.session.add(ans)
    else:
        ans.is_locked = True
        
    db.session.commit()
    
    # 2. Pošalji signal DIREKTNO tom igraču da mu se sivi ekran
    emit("player_lock_input", room=player_name) 
    
    # 3. Vrati adminu potvrdu
    emit("admin_lock_confirmed", {"player": player_name})

@socketio.on("admin_play_song")
def handle_play(d):
    s = Song.query.get(d["id"])
    if not s: return

    # 1. Logika za TV i Audio (već imaš)
    payload = {"round": s.round_number, "action": "playing", "type": s.type, "id": s.id}
    songs_in_r = Song.query.filter_by(quiz_id=s.quiz_id, round_number=s.round_number).order_by(Song.id).all()
    idx = next((i for i, song in enumerate(songs_in_r) if song.id == s.id), -1) + 1
    payload["song_index"] = idx

    if s.type == 'visual': payload["image"] = s.image_file
    if s.type == 'lyrics': payload["text"] = s.extra_data
    
    emit("screen_update_status", payload, broadcast=True)

    if s.filename:
        audio_data = {
            "url": url_for('stream_song', filename=s.filename),
            "start": s.start_time,
            "duration": s.duration
        }
        emit("play_audio", audio_data, broadcast=True)

    # 2. NOVO: Logika za IGRAČA (Otključaj unos)
    # Brišemo stare unose na frontendu i otvaramo polja
    emit("player_unlock_input", {
        "song_id": s.id, 
        "song_index": idx, 
        "round": s.round_number
    }, broadcast=True)


# NOVO: Admin zaključava rundu (kad timer istekne)
@socketio.on("admin_lock_round")
def handle_lock_round(data):
    # Javi svima da je gotovo
    emit("player_lock_input", broadcast=True)
    # Ovdje bi mogao i u bazi označiti da je pjesma/runda zaključana

# NOVO: Igrač šalje odgovor
@socketio.on("player_submit_answer")
def handle_player_answer(data):
    # data = { "song_id": 1, "artist": "...", "title": "...", "player_name": "..." }
    
    # Pronađi ili kreiraj odgovor u bazi
    # Pazimo da igrač ne može mijenjati ako je zaključano (provjera na serveru bi bila idealna)
    
    ans = Answer.query.filter_by(
        player_name=data['player_name'], 
        song_id=data['song_id']
    ).first()

    if not ans:
        ans = Answer(
            player_name=data['player_name'],
            song_id=data['song_id'],
            round_number=1 # Ovdje bi trebalo dohvatiti stvarnu rundu iz pjesme
        )
        # Dohvati rundu iz pjesme da budemo precizni
        song = Song.query.get(data['song_id'])
        if song: ans.round_number = song.round_number
        db.session.add(ans)
    
    # Ažuriraj odgovor
    ans.artist_guess = data.get('artist', '')
    ans.title_guess = data.get('title', '')
    db.session.commit()
    
    # Javi igraču da je spremljeno (opcionalno)
    # emit("answer_saved", to=request.sid)

@socketio.on("admin_confirm_player_score")
def confirm_player_score(data):
    emit("player_score_confirmed", data, broadcast=True)
    all_scores = {pl.name: pl.score for pl in Player.query.all()}
    emit("update_leaderboard", all_scores, broadcast=True)

@socketio.on("admin_show_results") # Ili sličan naziv eventa koji okidaš na gumb
def handle_show_results(data):
    round_num = data.get('round')
    
    # Dohvati sve pjesme te runde
    q = get_active_quiz()
    songs = Song.query.filter_by(quiz_id=q.id, round_number=round_num).all()
    
    answers_data = []
    for s in songs:
        answers_data.append({
            'artist': s.artist,
            'title': s.title
        })
        
    emit('screen_show_answers', {'answers': answers_data}, broadcast=True)

# --- OCJENJIVANJE ---

@socketio.on("admin_request_grading")
def handle_grading_request(data):
    round_num = data.get('round')
    quiz = get_active_quiz()
    
    # 1. Dohvati sve pjesme te runde
    songs = Song.query.filter_by(quiz_id=quiz.id, round_number=round_num).all()
    song_map = {s.id: s for s in songs}
    
    # 2. Dohvati sve odgovore
    answers = Answer.query.filter_by(round_number=round_num).all()
    
    grading_data = []
    
    # Grupiraj po igračima ili po pjesmama? 
    # Najbolje je poslati ravnu listu pa JS neka renderira tablicu
    for ans in answers:
        if ans.song_id not in song_map: continue
        
        song = song_map[ans.song_id]
        
        # Ako bodovi još nisu postavljeni (prvo otvaranje), izračunaj auto-grade
        # (Ovo radimo samo ako je rezultat 0, pretpostavljamo da nije ocjenjeno)
        # Možeš maknuti 'if' ako želiš da uvijek prebriše
        if ans.artist_points == 0 and ans.title_points == 0:
            ans.artist_points = 1.0 if calculate_similarity(ans.artist_guess, song.artist) >= 0.8 else 0.0
            ans.title_points = 1.0 if calculate_similarity(ans.title_guess, song.title) >= 0.8 else 0.0
            # Dodaj logiku za 0.5 bodova
            if ans.artist_points == 0 and calculate_similarity(ans.artist_guess, song.artist) >= 0.5: ans.artist_points = 0.5
            if ans.title_points == 0 and calculate_similarity(ans.title_guess, song.title) >= 0.5: ans.title_points = 0.5
            
        grading_data.append({
            "answer_id": ans.id,
            "player": ans.player_name,
            "song_index": songs.index(song) + 1, # Redni broj pjesme
            "artist_guess": ans.artist_guess,
            "title_guess": ans.title_guess,
            "correct_artist": song.artist,
            "correct_title": song.title,
            "artist_pts": ans.artist_points,
            "title_pts": ans.title_points
        })
    
    db.session.commit() # Spremi auto-grade
    
    # Pošalji podatke adminu
    emit("admin_receive_grading_data", grading_data)

@socketio.on("admin_update_score")
def handle_score_update(data):
    # Admin je kliknuo gumb (npr. promijenio bod za izvođača)
    ans = Answer.query.get(data['answer_id'])
    if ans:
        if data['type'] == 'artist':
            ans.artist_points = float(data['value'])
        else:
            ans.title_points = float(data['value'])
        db.session.commit()

@socketio.on("admin_finalize_round")
def handle_finalize_round(data):
    round_num = data.get('round')
    
    # 1. Zbroji bodove za sve igrače u ovoj rundi
    # Ovo je malo teže u SQLAlchmey bez raw SQL-a, pa ćemo pješke radi sigurnosti
    answers = Answer.query.filter_by(round_number=round_num).all()
    
    round_scores = {} # map: player_name -> score
    
    for a in answers:
        total = a.artist_points + a.title_points
        if a.player_name in round_scores:
            round_scores[a.player_name] += total
        else:
            round_scores[a.player_name] = total
            
    # 2. Ažuriraj ukupni rezultat igrača (Player tablica)
    # Pazi: Ovdje samo dodajemo. Ako želiš potpunu rekalkulaciju,
    # trebao bi proći kroz SVE odgovore ikad.
    # Za sada ćemo napraviti REKALKULACIJU SVIH RUNDI (najsigurnije)
    
    all_answers = Answer.query.all()
    player_totals = {}
    
    for a in all_answers:
        t = a.artist_points + a.title_points
        player_totals[a.player_name] = player_totals.get(a.player_name, 0) + t
        
    players = Player.query.all()
    for p in players:
        p.score = player_totals.get(p.name, 0.0)
        
    db.session.commit()
    
    # 3. Javi svima nove rezultate
    all_scores = {pl.name: pl.score for pl in Player.query.all()}
    emit("update_leaderboard", all_scores, broadcast=True)
    
    # Javi TV-u da prikaže točne odgovore
    handle_show_results({'round': round_num}) # Pozivamo postojeću funkciju

if __name__ == "__main__":
    ip = socket.gethostbyname(socket.gethostname())
    print(f"ROCK QUIZ READY ON {ip}:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)