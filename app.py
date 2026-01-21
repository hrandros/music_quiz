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
    Quiz.query.update({Quiz.is_active: False})
    db.session.add(Quiz(title=request.json.get("title"), is_active=True))
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/admin/scan_local_folder", methods=["POST"])
@login_required
def scan_local_folder():
    """Skenira mapu na disku koju je admin upisao i vraća popis MP3-a."""
    folder_path = request.json.get("path")
    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({"status": "error", "msg": "Mapa ne postoji ili putanja nije valjana."})
    mp3_files = []
    try:
        for f in os.listdir(folder_path):
            if f.lower().endswith('.mp3'):
                mp3_files.append(f)
        return jsonify({"status": "ok", "files": mp3_files})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route("/admin/import_external_song", methods=["POST"])
@login_required
def import_external_song():
    """Kopira pjesmu iz vanjske mape u 'songs' folder i dodaje je u kviz."""
    data = request.json
    source_path = data.get("source_path") # npr. D:/Music/song.mp3
    filename = data.get("filename")
    
    if not os.path.exists(source_path):
        return jsonify({"status": "error", "msg": "Izvorna datoteka ne postoji."})

    # Odredi ciljnu putanju u mapi 'songs'
    destination = os.path.join(DEFAULT_SONGS_DIR, filename)
    
    # Kopiraj datoteku
    try:
        shutil.copy2(source_path, destination)
    except Exception as e:
        return jsonify({"status": "error", "msg": f"Greška pri kopiranju: {str(e)}"})

    # Dodaj u bazu
    q = get_active_quiz()
    if not q:
        return jsonify({"status": "error", "msg": "Nema aktivnog kviza."})

    s = Song(
        quiz_id=q.id,
        filename=filename,
        artist="?",     # Admin će kasnije urediti
        title=filename.replace(".mp3", ""), # Defaultni naslov je ime fajla
        start_time=0.0,
        duration=15.0,
        round_number=int(data.get("round", 1))
    )
    db.session.add(s)
    db.session.commit()

    return jsonify({"status": "ok"})

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
    emit("join_success", {"name": p.name}, to=request.sid)
    all_scores = {pl.name: pl.score for pl in Player.query.all()}
    emit("update_leaderboard", all_scores, broadcast=True)

@socketio.on("admin_play_song")
def handle_play(d):
    s = Song.query.get(d["id"])
    if not s: return
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

@socketio.on("admin_confirm_player_score")
def confirm_player_score(data):
    emit("player_score_confirmed", data, broadcast=True)
    all_scores = {pl.name: pl.score for pl in Player.query.all()}
    emit("update_leaderboard", all_scores, broadcast=True)


if __name__ == "__main__":
    ip = socket.gethostbyname(socket.gethostname())
    print(f"ROCK QUIZ READY ON {ip}:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)