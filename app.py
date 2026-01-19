import os
import sys
import datetime
import socket
import requests
import subprocess
import json
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from difflib import SequenceMatcher
from werkzeug.utils import secure_filename

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
SNIPPETS_DIR = os.path.join(BASE_DIR, 'snippets')
DEFAULT_SONGS_DIR = os.path.join(BASE_DIR, 'songs')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")

os.makedirs(SNIPPETS_DIR, exist_ok=True)
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
    type = db.Column(db.String(20), default="standard") # standard, lyrics, visual, mashup
    filename = db.Column(db.String(200), nullable=True)
    image_file = db.Column(db.String(200), nullable=True)
    artist = db.Column(db.String(100), default="?")
    title = db.Column(db.String(100), default="?")
    extra_data = db.Column(db.String(500), default="") # Lyrics text ili Mashup artist 2
    start_time = db.Column(db.Integer, default=30)
    duration = db.Column(db.Integer, default=15)
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

def create_snippet(filename, start, dur):
    path = os.path.join(DEFAULT_SONGS_DIR, filename)
    out = os.path.join(SNIPPETS_DIR, f"cut_{filename}")
    if os.path.exists(out): return f"cut_{filename}"
    cmd = [FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else "ffmpeg", "-y", "-i", path, "-ss", str(start), "-t", str(dur), "-vn", "-acodec", "libmp3lame", out]
    try: subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return f"cut_{filename}"
    except: return None

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
    return render_template("admin_live.html", songs=songs)

@app.route("/admin/setup")
@login_required
def admin_setup():
    q = get_active_quiz()
    songs = Song.query.filter_by(quiz_id=q.id).order_by(Song.id).all() if q else []
    return render_template("admin_setup.html", quiz={"id": q.id if q else 0, "title": q.title if q else "", "songs": songs})

@app.route('/images/<filename>')
def serve_image(filename): return send_from_directory(IMAGES_DIR, filename)
@app.route('/snippets/<filename>')
def serve_snippet(filename): return send_from_directory(SNIPPETS_DIR, filename)
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

@app.route("/admin/add_song_advanced", methods=["POST"])
@login_required
def add_song_advanced():
    q = get_active_quiz()
    d = request.json
    s = Song(quiz_id=q.id, type=d.get("type"), filename=d.get("filename"), image_file=d.get("image_file"),
             artist=d.get("artist"), title=d.get("title"), extra_data=d.get("extra_data"),
             start_time=int(d.get("start_time",0)), duration=int(d.get("duration",15)), round_number=int(d.get("round",1)))
    db.session.add(s)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/admin/upload_image", methods=["POST"])
@login_required
def upload_image():
    f = request.files['file']
    fn = secure_filename(f"{datetime.datetime.now().timestamp()}_{f.filename}")
    f.save(os.path.join(IMAGES_DIR, fn))
    return jsonify({"filename": fn})

@app.route("/admin/scan_files")
@login_required
def scan_files():
    return jsonify([{"filename": f} for f in os.listdir(DEFAULT_SONGS_DIR) if f.lower().endswith(".mp3")])

@app.route("/admin/api_check_song", methods=["POST"])
@login_required
def api_check():
    q = request.json.get("filename").replace(".mp3","").replace("_"," ")
    try:
        r = requests.get(f"https://api.deezer.com/search?q={q}&limit=1").json()
        if r.get("data"): return jsonify({"found": True, "artist": r["data"][0]["artist"]["name"], "title": r["data"][0]["title"]})
    except: pass
    return jsonify({"found": False})

@app.route("/admin/remove_song", methods=["POST"])
@login_required
def remove_song():
    Song.query.filter_by(id=request.json.get("id")).delete()
    db.session.commit()
    return jsonify({"status": "ok"})

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
    
    # Send current round config to player so they can build the sheet
    # Assuming we know current round from context or default to 1
    # For robust solution, admin should emit 'round_start' but we can send data for all songs in active quiz
    # Here we just notify admin
    all_scores = {pl.name: pl.score for pl in Player.query.all()}
    emit("update_leaderboard", all_scores, broadcast=True)
    emit("admin_update_players", {"name": p.name, "score": p.score}, broadcast=True)

@socketio.on("player_update_answer")
def handle_draft(d):
    # Draft save
    ans = Answer.query.filter_by(player_name=d["name"], song_id=d["song_id"]).first()
    if not ans:
        ans = Answer(player_name=d["name"], round_number=d["round"], song_id=d["song_id"])
        db.session.add(ans)
    if not ans.is_locked:
        if d["type"] == 'artist': ans.artist_guess = d["value"]
        if d["type"] == 'title': ans.title_guess = d["value"]
        if d["type"] == 'extra': ans.extra_guess = d["value"]
        db.session.commit()

@socketio.on("admin_change_round")
def handle_round_change(d):
    q = get_active_quiz()
    # Get songs for this round to send config to players
    songs = Song.query.filter_by(quiz_id=q.id, round_number=d["round"]).order_by(Song.id).all()
    config = [{"id": s.id, "type": s.type, "extra": s.extra_data} for s in songs]
    
    emit("screen_update_status", {"round": d["round"], "action": "round_change"}, broadcast=True)
    emit("player_round_config", {"round": d["round"], "songs": config}, broadcast=True)

@socketio.on("admin_play_song")
def handle_play(d):
    s = Song.query.get(d["id"])
    payload = {"round": s.round_number, "action": "playing", "type": s.type}
    if s.filename:
        f = create_snippet(s.filename, s.start_time, s.duration)
        if f: emit("play_audio", {"file": f}, broadcast=True)
    if s.type == 'visual': payload["image"] = s.image_file
    if s.type == 'lyrics': payload["text"] = s.extra_data
    emit("screen_update_status", payload, broadcast=True)

@socketio.on("admin_lock_round")
def lock_round(d):
    r = d["round"]
    q = get_active_quiz()
    songs = Song.query.filter_by(quiz_id=q.id, round_number=r).all()
    correct = {s.id: s for s in songs}
    
    # Auto grade
    answers = Answer.query.filter_by(round_number=r).all()
    for a in answers:
        a.is_locked = True
        if a.song_id in correct:
            c = correct[a.song_id]
            if a.artist_points == 0: a.artist_points = calculate_similarity(a.artist_guess, c.artist)
            if a.title_points == 0: a.title_points = calculate_similarity(a.title_guess, c.title)
    db.session.commit()
    
    # Recalc scores
    for p in Player.query.all():
        p.score = sum([x.artist_points + x.title_points + x.extra_points for x in Answer.query.filter_by(player_name=p.name).all()])
    db.session.commit()

    emit("round_locked", {"round": r}, broadcast=True)
    
    # Send grading data to admin
    g_data = []
    answers = Answer.query.filter_by(round_number=r).all()
    for a in answers:
        c = correct.get(a.song_id)
        g_data.append({
            "player": a.player_name, "song_id": a.song_id,
            "artist_guess": a.artist_guess, "title_guess": a.title_guess,
            "artist_pts": a.artist_points, "title_pts": a.title_points,
            "c_artist": c.artist if c else "?", "c_title": c.title if c else "?"
        })
    emit("admin_grading_data", g_data, broadcast=True)
    
    # Show answers on screen
    s_data = [{"artist": s.artist, "title": s.title} for s in songs]
    emit("screen_show_answers", {"round": r, "answers": s_data}, broadcast=True)

@socketio.on("admin_grade_answer")
def grade(d):
    a = Answer.query.filter_by(player_name=d["player"], song_id=d["song_id"]).first()
    if a:
        if "artist_pts" in d: a.artist_points = d["artist_pts"]
        if "title_pts" in d: a.title_points = d["title_pts"]
        db.session.commit()
        # Update player score
        p = Player.query.filter_by(name=a.player_name).first()
        p.score = sum([x.artist_points + x.title_points for x in Answer.query.filter_by(player_name=p.name).all()])
        db.session.commit()
        # Emit individual feedback to player
        emit("grade_update", {"song_id": a.song_id, "artist_pts": a.artist_points, "title_pts": a.title_points}, broadcast=True)
        # Emit leaderboard
        emit("update_leaderboard", {pl.name: pl.score for pl in Player.query.all()}, broadcast=True)

@socketio.on("player_activity_status")
def anti_cheat(d): emit("admin_player_status_change", d, broadcast=True)
@socketio.on("admin_connect")
def adm_con(): emit("update_leaderboard", {pl.name: pl.score for pl in Player.query.all()})

if __name__ == "__main__":
    ip = socket.gethostbyname(socket.gethostname())
    print(f"ROCK QUIZ READY ON {ip}:5000")
    socketio.run(app, host="0.0.0.0", port=5000)