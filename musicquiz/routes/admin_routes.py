
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
from musicquiz.models import (
    Quiz,
    Question,
    Song,
    Video,
    TextQuestion,
    TextMultiple,
    SimultaneousQuestion,
)
from musicquiz.services.quiz_service import get_active_quiz
from musicquiz.services.deezer_service import query_deezer_metadata
from musicquiz.services.question_service import get_question_display
from config import Config
from sqlalchemy import func

admin_bp = Blueprint("admin", __name__)


def _get_next_position(quiz_id, round_number):
    max_pos = db.session.query(func.max(Question.position)) \
        .filter(Question.quiz_id == quiz_id) \
        .filter(Question.round_number == round_number) \
        .scalar()
    return (max_pos or 0) + 1


def _validate_round(round_number):
    return 1 <= int(round_number) <= 5


def _get_question_list(quiz_id):
    questions = Question.query.filter_by(quiz_id=quiz_id).order_by(
        Question.round_number,
        Question.position
    ).all()
    return [get_question_display(q) for q in questions]


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
    songs = _get_question_list(q.id) if q else []
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
    songs = _get_question_list(q.id) if q else []

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

        
        round_num = int(data.get("round", 1))
        if not _validate_round(round_num):
            return jsonify({"status": "error", "msg": "Round must be between 1 and 5"}), 400

        next_order = _get_next_position(q.id, round_num)


        safe_name = secure_filename(pure_filename)

        destination = os.path.join(Config.SONGS_DIR, safe_name)

        shutil.copy2(source_path, destination)

        question = Question(
            quiz_id=q.id,
            round_number=round_num,
            position=next_order,
            type="audio",
            duration=30.0,
        )
        db.session.add(question)
        db.session.flush()

        s = Song(
            question_id=question.id,
            filename=safe_name,
            artist=artist,
            title=title,
            start_time=0.0,
        )

        db.session.add(s)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "song": get_question_display(question)
        })

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})



# -------------------
# REMOVE SONG
# -------------------
@admin_bp.route("/remove_song", methods=["POST"])
@login_required
def remove_song():
    from musicquiz.models import Answer

    question_id = request.json.get("id")
    Answer.query.filter_by(question_id=question_id).delete()
    question = Question.query.get(question_id)
    if question:
        db.session.delete(question)
    db.session.commit()
    return jsonify({"status": "ok"})


# -------------------
# UPDATE SONG
# -------------------
@admin_bp.route("/update_song", methods=["POST"])
@login_required
def update_song():
    data = request.json
    question = Question.query.get(data.get("id"))

    if not question:
        return jsonify({"status": "error", "msg": "Question not found"}), 404

    if question.type != "audio" or not question.song:
        return jsonify({"status": "error", "msg": "Only audio questions can be edited here"}), 400

    song = question.song

    song.artist = data.get("artist")
    song.title = data.get("title")
    song.start_time = float(data.get("start"))
    question.duration = float(data.get("duration"))

    db.session.commit()
    return jsonify({"status": "ok"})


@admin_bp.route("/api/update_score", methods=["POST"])
@login_required
def api_update_score():
    """API endpoint za ažuriranje bodova iz grading tablice."""
    try:
        from musicquiz.models import Answer

        data = request.json
        answer_id = data.get("answer_id")
        score_type = data.get("type")
        score_value = float(data.get("value", -1))

        # Validacija
        if score_value not in [0, 0.5, 1.0]:
            return jsonify({"status": "error", "msg": "Invalid score value"}), 400

        if score_type not in ["artist", "title", "extra"]:
            return jsonify({"status": "error", "msg": "Invalid score type"}), 400

        ans = Answer.query.get(answer_id)
        if not ans:
            return jsonify({"status": "error", "msg": "Answer not found"}), 404

        if score_type == "artist":
            ans.artist_points = score_value
        elif score_type == "title":
            ans.title_points = score_value
        else:
            ans.extra_points = score_value

        db.session.commit()
        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# -------------------
# REORDER SONGS
# -------------------
@admin_bp.route("/reorder_songs", methods=["POST"])
@login_required
def reorder_songs():
    """Ažurira poziciju pjesama na osnovu redoslijeda iz drag-and-drop."""
    try:
        data = request.json
        ids = data.get("ids", [])

        if not ids:
            return jsonify({"status": "error", "msg": "No IDs provided"}), 400

        questions = Question.query.filter(Question.id.in_(ids)).all()
        question_map = {q.id: q for q in questions}
        round_counters = {}
        updated = []

        for qid in ids:
            question = question_map.get(qid)
            if not question:
                continue
            round_num = question.round_number
            round_counters[round_num] = round_counters.get(round_num, 0) + 1
            question.position = round_counters[round_num]
            updated.append({
                "id": question.id,
                "round_number": round_num,
                "position": question.position,
            })

        db.session.commit()
        return jsonify({"status": "ok", "updated": updated})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# -------------------
# CREATE QUESTION TYPES
# -------------------

@admin_bp.route("/create_text_question", methods=["POST"])
@login_required
def create_text_question():
    """Create a text answer question."""
    try:
        data = request.json
        q = get_active_quiz()
        if not q:
            return jsonify({"status": "error", "msg": "No active quiz"}), 400

        round_num = int(data.get("round", 1))
        question_text = data.get("question_text", "")
        answer_text = data.get("answer_text", "")

        if not _validate_round(round_num):
            return jsonify({"status": "error", "msg": "Round must be between 1 and 5"}), 400

        if not question_text or not answer_text:
            return jsonify({"status": "error", "msg": "Question text and answer are required"}), 400

        next_pos = _get_next_position(q.id, round_num)

        question = Question(
            quiz_id=q.id,
            type="text",
            round_number=round_num,
            position=next_pos,
            duration=float(data.get("duration", 30.0))
        )
        db.session.add(question)
        db.session.flush()

        text_row = TextQuestion(
            question_id=question.id,
            question_text=question_text,
            answer_text=answer_text,
        )
        db.session.add(text_row)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "song": get_question_display(question)
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@admin_bp.route("/create_multiple_choice_question", methods=["POST"])
@login_required
def create_multiple_choice_question():
    """Create a multiple choice question."""
    try:
        data = request.json
        q = get_active_quiz()
        if not q:
            return jsonify({"status": "error", "msg": "No active quiz"}), 400

        round_num = int(data.get("round", 1))
        question_text = data.get("question_text", "")
        choices = data.get("choices", [])
        correct_idx = int(data.get("correct_idx", 0))

        if not _validate_round(round_num):
            return jsonify({"status": "error", "msg": "Round must be between 1 and 5"}), 400

        if not question_text or not choices or len(choices) < 2:
            return jsonify({"status": "error", "msg": "Need question text and 2+ choices"}), 400

        next_pos = _get_next_position(q.id, round_num)

        question = Question(
            quiz_id=q.id,
            type="text_multiple",
            round_number=round_num,
            position=next_pos,
            duration=float(data.get("duration", 30.0))
        )
        db.session.add(question)
        db.session.flush()

        text_row = TextMultiple(
            question_id=question.id,
            question_text=question_text,
            correct_index=correct_idx,
        )
        text_row.set_choices(choices)
        db.session.add(text_row)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "song": get_question_display(question)
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@admin_bp.route("/create_video_question", methods=["POST"])
@login_required
def create_video_question():
    """Create a video question."""
    try:
        data = request.json
        q = get_active_quiz()
        if not q:
            return jsonify({"status": "error", "msg": "No active quiz"}), 400

        round_num = int(data.get("round", 1))
        filename = data.get("filename", "")
        artist = data.get("artist", "?")
        title = data.get("title", "?")

        if not _validate_round(round_num):
            return jsonify({"status": "error", "msg": "Round must be between 1 and 5"}), 400

        if not filename:
            return jsonify({"status": "error", "msg": "Video filename is required"}), 400

        next_pos = _get_next_position(q.id, round_num)

        question = Question(
            quiz_id=q.id,
            type="video",
            round_number=round_num,
            position=next_pos,
            duration=float(data.get("duration", 30.0))
        )
        db.session.add(question)
        db.session.flush()

        video = Video(
            question_id=question.id,
            filename=filename,
            artist=artist,
            title=title,
            start_time=float(data.get("start_time", 0.0)),
        )
        db.session.add(video)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "song": get_question_display(question)
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@admin_bp.route("/create_simultaneous_question", methods=["POST"])
@login_required
def create_simultaneous_question():
    """Create a simultaneous (audio + text) question."""
    try:
        data = request.json
        q = get_active_quiz()
        if not q:
            return jsonify({"status": "error", "msg": "No active quiz"}), 400

        round_num = int(data.get("round", 1))
        filename = data.get("filename", "")
        artist = data.get("artist", "?")
        title = data.get("title", "?")
        extra_question = data.get("extra_question", "")
        extra_answer = data.get("extra_answer", "")

        if not _validate_round(round_num):
            return jsonify({"status": "error", "msg": "Round must be between 1 and 5"}), 400

        if not filename:
            return jsonify({"status": "error", "msg": "Audio filename is required"}), 400

        if extra_question and not extra_answer:
            return jsonify({"status": "error", "msg": "Extra answer is required"}), 400

        next_pos = _get_next_position(q.id, round_num)

        question = Question(
            quiz_id=q.id,
            type="simultaneous",
            round_number=round_num,
            position=next_pos,
            duration=float(data.get("duration", 30.0))
        )
        db.session.add(question)
        db.session.flush()

        simultaneous = SimultaneousQuestion(
            question_id=question.id,
            filename=filename,
            artist=artist,
            title=title,
            start_time=float(data.get("start_time", 0.0)),
            extra_question=extra_question,
            extra_answer=extra_answer,
        )
        db.session.add(simultaneous)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "song": get_question_display(question)
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500