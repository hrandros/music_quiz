
import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog

from flask import (
    Blueprint, render_template, request, jsonify, session,
    redirect, url_for, flash
)

from werkzeug.utils import secure_filename

from extensions import db
from musicquiz.models import Quiz, Song
from musicquiz.services.quiz_service import get_active_quiz
from musicquiz.services.deezer_service import query_deezer_metadata
from config import Config
from sqlalchemy import func

admin_bp = Blueprint("admin", __name__)


# -------------------
# LOGIN REQUIRED
# -------------------
from functools import wraps
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return wrapped


# -------------------
# LOGIN PAGE
# -------------------
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == Config.ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin.admin_live"))
        flash("Kriva lozinka!", "danger")

    return render_template("login.html")


# -------------------
# ADMIN MAIN PAGES
# -------------------
@admin_bp.route("/live")
@login_required
def admin_live():
    q = get_active_quiz()
    # Pošalji i sve kvizove kako bi admin mogao prebacivati aktivni kviz
    all_q = Quiz.query.order_by(Quiz.id.desc()).all()
    songs = Song.query.filter_by(quiz_id=q.id).order_by(Song.song_position).all() if q else []
    return render_template("admin_live.html", all_songs=songs, quiz=q, all_quizzes=all_q)


@admin_bp.route('/switch_quiz', methods=['POST'])
@login_required
def switch_quiz():
    try:
        qid = int(request.json.get('id', 0))
    except Exception:
        return jsonify({'status': 'error', 'msg': 'Invalid id'}), 400

    # Deaktiviraj sve i aktiviraj odabrani
    Quiz.query.update({Quiz.is_active: False})
    quiz = Quiz.query.get(qid)
    if not quiz:
        return jsonify({'status': 'error', 'msg': 'Quiz not found'}), 404
    quiz.is_active = True
    db.session.commit()
    return jsonify({'status': 'ok'})


@admin_bp.route("/setup")
@login_required
def admin_setup():
    q = get_active_quiz()
    all_q = Quiz.query.all()
    songs = Song.query.filter_by(quiz_id=q.id).order_by(Song.song_position).all() if q else []

    return render_template(
        "admin_setup.html",
        quiz=q,
        all_quizzes=all_q,
        songs=songs
    )


# -------------------
# CREATE QUIZ
# -------------------
@admin_bp.route("/create_quiz", methods=["POST"])
@login_required
def create_quiz():
    Quiz.query.update({Quiz.is_active: False})

    title = request.json.get("title", "")
    date_str = (request.json.get("date") or "").strip()

    event_date = None
    if date_str:
        try:
            from datetime import datetime
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return jsonify({"status": "error", "msg": "Neispravan format datuma (očekuje YYYY-MM-DD)."}), 400

    if event_date is None:
        new_quiz = Quiz(title=title, is_active=True)
    else:
        new_quiz = Quiz(title=title, event_date=event_date, is_active=True)

    db.session.add(new_quiz)
    db.session.commit()

    return jsonify({"status": "ok"})


# -------------------
# API DEEZER LOOKUP
# -------------------
@admin_bp.route("/api_check_deezer", methods=["POST"])
@login_required
def api_check_deezer():
    filename = request.json.get("filename", "")

    # Obrada imena kao u originalnom kodu
    query = re.sub(r'\.mp3$', '', filename, flags=re.IGNORECASE)
    query = re.sub(r'^\d+[ _\.-]+', '', query)
    query = query.replace('_', ' ').replace('-', ' ')

    result = query_deezer_metadata(query)
    return jsonify(result)


# -------------------
# PICK FOLDER (TKINTER)
# -------------------
@admin_bp.route("/open_folder_picker", methods=["GET"])
@login_required
def open_folder_picker():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        path = filedialog.askdirectory(title="Odaberi mapu s glazbom")
        root.destroy()

        if not path:
            return jsonify({"status": "cancel"})

        path = path.replace("\\", "/")
        return jsonify({"status": "ok", "path": path})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})


# -------------------
# SCAN LOCAL FOLDER
# -------------------
@admin_bp.route("/scan_local_folder", methods=["POST"])
@login_required
def scan_local_folder():
    raw_path = request.json.get("path")

    if not raw_path:
        return jsonify({"status": "error", "msg": "Putanja nije definirana."})

    folder_path = raw_path.strip('"\'').strip()

    if not os.path.isdir(folder_path):
        return jsonify({
            "status": "error",
            "msg": f"Mapa ne postoji na putanji: {folder_path}"
        })

    mp3_files = []

    try:
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(".mp3"):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, folder_path)
                    mp3_files.append(rel.replace("\\", "/"))

        mp3_files.sort()
        return jsonify({"status": "ok", "files": mp3_files})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})


# -------------------
# IMPORT EXTERNAL SONG
# -------------------
@admin_bp.route("/import_external_song", methods=["POST"])
@login_required
def import_external_song():
    try:
        data = request.json
        source_path = data.get("source_path")
        rel_path = data.get("filename")

        pure_filename = os.path.basename(rel_path)
        clean_name = os.path.splitext(pure_filename)[0].replace("_", " ").replace("-", " ")

        artist = data.get("artist") or "Nepoznato"
        title = data.get("title") or clean_name

        q = get_active_quiz()

        
        max_order = db.session.query(func.max(Song.song_position)) \
            .filter(Song.quiz_id == q.id) \
            .scalar()
        next_order = (max_order or 0) + 1   


        safe_name = secure_filename(pure_filename)

        destination = os.path.join(Config.SONGS_DIR, safe_name)

        shutil.copy2(source_path, destination)

        s = Song(
            quiz_id=q.id,
            song_position=next_order,
            filename=safe_name,
            artist=artist,
            title=title,
            start_time=0.0,
            duration=30.0,
            round_number=int(data.get("round", 1))
        )

        db.session.add(s)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "song": {
                "id": s.id,
                "order": s.song_position,
                "artist": s.artist,
                "title": s.title,
                "filename": s.filename,
                "start": s.start_time,
                "duration": s.duration,
                "round": s.round_number
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})



# -------------------
# REMOVE SONG
# -------------------
@admin_bp.route("/remove_song", methods=["POST"])
@login_required
def remove_song():
    Song.query.filter_by(id=request.json.get("id")).delete()
    db.session.commit()
    return jsonify({"status": "ok"})


# -------------------
# UPDATE SONG
# -------------------
@admin_bp.route("/update_song", methods=["POST"])
@login_required
def update_song():
    data = request.json
    song = Song.query.get(data.get("id"))

    if not song:
        return jsonify({"status": "error", "msg": "Song not found"}), 404

    song.artist = data.get("artist")
    song.title = data.get("title")
    song.start_time = float(data.get("start"))
    song.duration = float(data.get("duration"))

    db.session.commit()
    return jsonify({"status": "ok"})