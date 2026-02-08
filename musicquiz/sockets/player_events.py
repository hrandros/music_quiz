from extensions import db
import time
from flask_socketio import emit, join_room
from musicquiz.models import Player, Answer, Question
from musicquiz.sockets.admin_events import quiz_settings, get_active_question_state
from flask import request

def register_player_events(socketio):

    locked_players = set()

    # ---------------------------
    # PLAYER JOIN
    # ---------------------------
    @socketio.on("player_join")
    def handle_join(data):
        active_state = get_active_question_state()
        if not quiz_settings["registrations_open"] and not quiz_settings.get("quiz_started"):
            emit("join_error", {"msg": "Prijava još nije otvorena! Slobodno naručite nešto za popiti."}, to=request.sid)
            return
        name = data["name"]
        pin = data.get("pin", "0000")

        if name in locked_players:
            emit("join_error", {"msg": "Vaš tim je zaključan za ovaj kviz."}, to=request.sid)
            return

        player = Player.query.filter_by(name=name).first()

        if not player:
            player = Player(name=name, pin=pin)
            db.session.add(player)
        else:
            if player.pin != pin:
                emit("join_error", {"msg": "Krivi PIN!"}, to=request.sid)
                return

        db.session.commit()

        # player active
        from musicquiz.services.player_status import live_player_status
        live_player_status[name] = "active"

        join_room(name)
        emit("join_success", {"name": name}, to=request.sid)

        all_players = Player.query.all()
        leaderboard = {p.name: p.score for p in all_players}
        
        # Koristimo socketio.emit (bez to=) da ode svim klijentima, uključujući TV Screen
        socketio.emit("update_leaderboard", leaderboard)

        # Update admin
        from musicquiz.services.player_status import get_all_players_data
        socketio.emit("admin_update_player_list", get_all_players_data())

        if active_state:
            question = Question.query.get(active_state["question_id"])
            if question:
                from musicquiz.services.question_service import get_question_unlock_payload
                payload = get_question_unlock_payload(question)
                payload["question_started_at"] = active_state["started_at"]
                payload["question_duration"] = active_state["duration"]
                emit("player_unlock_input", payload, to=request.sid)

    # ---------------------------
    # PLAYER ACTIVITY UPDATE
    # ---------------------------
    @socketio.on("player_activity_status")
    def handle_activity(data):
        name = data.get("name")
        status = data.get("status")

        from musicquiz.services.player_status import live_player_status
        live_player_status[name] = status

        emit(
            "admin_single_player_update",
            {"name": name, "status": status}
        )

    # ---------------------------
    # PLAYER SUBMIT ANSWER
    # ---------------------------
    @socketio.on("player_submit_answer")
    def handle_player_answer(data):
        player_name = data["player_name"]
        if player_name in locked_players:
            return
        question_id = data["question_id"]
        question = Question.query.get(question_id)
        if not question:
            return

        active_state = get_active_question_state()
        if not active_state or active_state.get("question_id") != question_id:
            return

        submission_time = max(0.0, time.time() - active_state.get("started_at", time.time()))
        if submission_time > active_state.get("duration", 0):
            return

        ans = Answer.query.filter_by(
            player_name=player_name,
            question_id=question_id
        ).first()

        if not ans:
            # Create new answer record
            ans = Answer(
                player_name=player_name,
                question_id=question_id
            )
            ans.round_number = question.round_number
            db.session.add(ans)

        # Store submission time (in seconds)
        ans.submission_time = float(submission_time)

        # Update fields based on question type
        question_type = question.type or "audio"
        ans.artist_guess = ""
        ans.title_guess = ""
        ans.extra_guess = ""
        ans.choice_selected = -1

        if question_type in ["audio", "video"]:
            ans.artist_guess = data.get("artist", "")
            ans.title_guess = data.get("title", "")
        elif question_type == "text":
            ans.title_guess = data.get("title", "")
        elif question_type == "text_multiple":
            ans.choice_selected = int(data.get("choice", -1))
        elif question_type == "simultaneous":
            ans.artist_guess = data.get("artist", "")
            ans.title_guess = data.get("title", "")
            ans.extra_guess = data.get("extra", "")

        db.session.commit()

        # Broadcast updated grading data to admin immediately
        from musicquiz.sockets.admin_events import broadcast_grading_data
        broadcast_grading_data()

    # ---------------------------
    # PLAYER CHEAT DETECTED
    # ---------------------------
    @socketio.on("player_cheat_detected")
    def handle_player_cheat(data):
        player_name = data.get("player_name")
        if not player_name:
            return
        locked_players.add(player_name)

        from musicquiz.services.player_status import live_player_status, get_all_players_data
        live_player_status[player_name] = "locked"
        socketio.emit("admin_update_player_list", get_all_players_data())
        emit("player_lock_input", room=player_name)