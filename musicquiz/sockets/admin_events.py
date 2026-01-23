
from extensions import db,socketio
from flask_socketio import emit
from musicquiz.models import Player, Song, Answer
from musicquiz.services.quiz_service import get_active_quiz
from musicquiz.services.player_status import get_all_players_data
from musicquiz.services.grading_service import auto_grade_answer
import time

current_state = {"round": None, "song_id": None, "locked": False}

def start_server_timer(seconds, round_num):
    def task():
        remaining = int(seconds)
        while remaining > 0:
            socketio.emit("timer_tick", {"sec": remaining}, broadcast=True)
            time.sleep(1)
            remaining -= 1
        # time's up -> lock
        current_state["locked"] = True
        socketio.emit("player_lock_input", broadcast=True)
    socketio.start_background_task(task)

@socketio.on("admin_start_round_timer")
def handle_start_round_timer(data):
    seconds = int(data.get("sec", 30))
    round_num = int(data.get("round", 1))
    current_state["round"] = round_num
    current_state["locked"] = False
    start_server_timer(seconds, round_num)


def register_admin_events(socketio):

    # ---------------------------
    # REQUEST FULL PLAYER LIST
    # ---------------------------
    @socketio.on("admin_get_players")
    def handle_get_players():
        emit("admin_player_list_full", get_all_players_data())

    # ---------------------------
    # LOCK SINGLE PLAYER INPUT
    # ---------------------------
    @socketio.on("admin_lock_single_player")
    def handle_single_lock(data):
        player_name = data.get("player_name")
        song_id = data.get("song_id")

        ans = Answer.query.filter_by(
            player_name=player_name,
            song_id=song_id
        ).first()

        if not ans:
            song = Song.query.get(song_id)
            if song:
                ans = Answer(
                    player_name=player_name,
                    song_id=song_id,
                    round_number=song.round_number,
                    is_locked=True
                )
                db.session.add(ans)
        else:
            ans.is_locked = True

        db.session.commit()

        emit("player_lock_input", room=player_name)
        emit("admin_lock_confirmed", {"player": player_name})

    # ---------------------------
    # ADMIN PLAY SONG
    # ---------------------------
    @socketio.on("admin_play_song")
    def handle_play(data):
        s = Song.query.get(data["id"])
        if not s:
            return

        qid = s.quiz_id
        songs_in_round = Song.query.filter_by(
            quiz_id=qid,
            round_number=s.round_number
        ).order_by(Song.id).all()

        idx = next(
            (i + 1 for i, song in enumerate(songs_in_round) if song.id == s.id),
            None
        )

        payload = {
            "round": s.round_number,
            "action": "playing",
            "type": s.type,
            "id": s.id,
            "song_index": idx
        }

        if s.type == "visual":
            payload["image"] = s.image_file
        if s.type == "lyrics":
            payload["text"] = s.extra_data

        emit("screen_update_status", payload, broadcast=True)

        if s.filename:
            from flask import url_for
            audio_data = {
                "url": url_for("file.stream_song", filename=s.filename),
                "start": s.start_time,
                "duration": s.duration
            }
            emit("play_audio", audio_data, broadcast=True)

        emit(
            "player_unlock_input",
            {"song_id": s.id, "song_index": idx, "round": s.round_number},
            broadcast=True
        )

    # ---------------------------
    # LOCK ENTIRE ROUND
    # ---------------------------
    @socketio.on("admin_lock_round")
    def handle_lock_round(data):
        emit("player_lock_input", broadcast=True)

    # ---------------------------
    # REQUEST GRADING DATA
    # ---------------------------
    @socketio.on("admin_request_grading")
    def handle_grading_request(data):
        round_num = data.get("round")
        quiz = get_active_quiz()

        songs = Song.query.filter_by(
            quiz_id=quiz.id,
            round_number=round_num
        ).all()

        song_map = {s.id: s for s in songs}
        answers = Answer.query.filter_by(round_number=round_num).all()

        grading_data = []

        for ans in answers:
            if ans.song_id not in song_map:
                continue

            song = song_map[ans.song_id]

            auto_grade_answer(ans, song)
            db.session.commit()

            grading_data.append({
                "answer_id": ans.id,
                "player": ans.player_name,
                "song_index": songs.index(song) + 1,
                "artist_guess": ans.artist_guess,
                "title_guess": ans.title_guess,
                "correct_artist": song.artist,
                "correct_title": song.title,
                "artist_pts": ans.artist_points,
                "title_pts": ans.title_points
            })

        emit("admin_receive_grading_data", grading_data)

    # ---------------------------
    # UPDATE INDIVIDUAL SCORE
    # ---------------------------
    @socketio.on("admin_update_score")
    def handle_score_update(data):
        ans = Answer.query.get(data["answer_id"])
        if ans:
            if data["type"] == "artist":
                ans.artist_points = float(data["value"])
            else:
                ans.title_points = float(data["value"])
            db.session.commit()

    # ---------------------------
    # FINALIZE ROUND
    # ---------------------------
    @socketio.on("admin_finalize_round")
    def handle_finalize_round(data):
        round_num = data.get("round")

        all_answers = Answer.query.all()
        totals = {}

        for a in all_answers:
            pts = a.artist_points + a.title_points
            totals[a.player_name] = totals.get(a.player_name, 0) + pts

        players = Player.query.all()
        for p in players:
            p.score = totals.get(p.name, 0.0)
        db.session.commit()

        leaderboard = {p.name: p.score for p in Player.query.all()}
        emit("update_leaderboard", leaderboard, broadcast=True)

        handle_show_results({"round": round_num})

    # ---------------------------
    # SHOW RESULTS (TV SCREEN)
    # ---------------------------
    @socketio.on("admin_show_results")
    def handle_show_results(data):
        round_num = data.get("round")

        quiz = get_active_quiz()
        songs = Song.query.filter_by(
            quiz_id=quiz.id,
            round_number=round_num
        ).all()

        answers_data = [{"artist": s.artist, "title": s.title} for s in songs]

        emit("screen_show_answers", {"answers": answers_data}, broadcast=True)

    # ---------------------------
    # CONFIRM SCORE TO PLAYER
    # ---------------------------
    @socketio.on("admin_confirm_player_score")
    def confirm_player_score(data):
        emit("player_score_confirmed", data, broadcast=True)

        leaderboard = {p.name: p.score for p in Player.query.all()}
        emit("update_leaderboard", leaderboard, broadcast=True)


