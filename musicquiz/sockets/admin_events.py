from extensions import db, socketio
from flask_socketio import emit
from flask import current_app, request, url_for
from musicquiz.models import Player, Question, Answer
from musicquiz.services.quiz_service import get_active_quiz
from musicquiz.services.player_status import get_all_players_data
from musicquiz.services.grading_service import grade_answer_for_question
from musicquiz.services.question_service import (
    get_question_answer_key,
    get_question_display,
    get_question_media,
    get_question_unlock_payload,
)
import time

# Globalno stanje kviza
quiz_settings = {
    "registrations_open": False,
    "quiz_paused": False,
    "quiz_started": False,
    "current_question_id": None,
    "current_question_started_at": None,
    "current_question_duration": None,
    "current_question_phase": None,
}

live_armed_clients = set()


def get_active_question_state():
    if not quiz_settings.get("current_question_id"):
        return None
    if quiz_settings.get("current_question_phase") != "question":
        return None
    started_at = quiz_settings.get("current_question_started_at")
    duration = quiz_settings.get("current_question_duration")
    if not started_at or not duration:
        return None
    elapsed = time.time() - started_at
    remaining = duration - elapsed
    if remaining <= 0:
        return None
    return {
        "question_id": quiz_settings.get("current_question_id"),
        "started_at": started_at,
        "duration": duration,
        "remaining": remaining,
    }

# --- POMOĆNE FUNKCIJE ---

def get_question_index(question):
    """Vraća redni broj pitanja unutar runde."""
    questions = Question.query.filter_by(
        quiz_id=question.quiz_id,
        round_number=question.round_number
    ).order_by(Question.position).all()
    return next((i + 1 for i, q in enumerate(questions) if q.id == question.id), 1)

def get_max_points(question):
    if not question:
        return 0
    if question.type in ["audio", "video"]:
        return 2
    if question.type in ["text", "text_multiple"]:
        return 1
    if question.type == "simultaneous":
        if question.simultaneous and question.simultaneous.extra_answer:
            return 3
        return 2
    return 0

def calculate_and_broadcast_leaderboard():
    """Centralna funkcija za izračun bodova i slanje ljestvice na TV."""
    all_players = Player.query.all()
    leaderboard = {}
    
    # Prvo ažuriramo bazu za svakog igrača
    for p in all_players:
        # Sumiramo sve bodove iz tablice Answer za tog igrača
        pts = db.session.query(db.func.sum(Answer.artist_points + Answer.title_points + Answer.extra_points))\
                .filter(Answer.player_name == p.name).scalar() or 0
        p.score = float(pts)
        leaderboard[p.name] = p.score
    
    db.session.commit()
    socketio.emit("update_leaderboard", leaderboard)
    return leaderboard

def broadcast_grading_data():
    """Prikuplja sve odgovore za trenutno aktivnu pjesmu i šalje ih adminu."""
    quiz = get_active_quiz()
    active_questions = Question.query.filter_by(quiz_id=quiz.id).all()
    question_ids = [q.id for q in active_questions]
    
    answers = Answer.query.filter(Answer.question_id.in_(question_ids)).all()
    
    grading_payload = []
    for ans in answers:
        question = Question.query.get(ans.question_id)
        grading_payload.append({
            "id": ans.id,
            "player_name": ans.player_name,
            "artist_guess": ans.artist_guess,
            "title_guess": ans.title_guess,
            "extra_guess": ans.extra_guess,
            "artist_points": float(ans.artist_points),
            "title_points": float(ans.title_points),
            "extra_points": float(ans.extra_points),
            "question_id": ans.question_id,
            "round_number": question.round_number if question else 0,
            "position": question.position if question else 0,
            "question_type": question.type if question else ""
        })
    
    # Šaljemo samo adminima
    socketio.emit("admin_receive_grading_data", grading_payload)

def finalize_round(round_num):
    """Završni auto-grade za cijelu rundu i finalno slanje ljestvice."""
    try:
        quiz = get_active_quiz()
        questions = Question.query.filter_by(quiz_id=quiz.id, round_number=round_num).all()
        question_map = {q.id: q for q in questions}

        answers = Answer.query.filter_by(round_number=round_num).all()
        for ans in answers:
            if ans.question_id in question_map:
                try:
                    grade_answer_for_question(ans, question_map[ans.question_id])
                except Exception as e:
                    print(f"Warning: Failed to auto-grade answer {ans.id}: {str(e)}")

        db.session.commit()
        calculate_and_broadcast_leaderboard()
    except Exception as e:
        print(f"Error in finalize_round: {str(e)}")

# --- GLAVNA LOGIKA KVIZA ---

def auto_quiz_sequence(question_id, round_num, app):
    """Automatska petlja: Pitanje -> Lock -> Rezultat -> Bodovanje -> Next."""
    with app.app_context():
        question = Question.query.get(question_id)
        if not question:
            return

        answer_display_seconds = 15

        idx = get_question_index(question)

        media = get_question_media(question)
        media_url = media.get("url", "")
        media_start = media.get("start", 0.0)

        total_songs = Question.query.filter_by(
            quiz_id=question.quiz_id,
            round_number=round_num
        ).count()

        # 1. EMITIRAJ POČETAK PJESME
        question_display = get_question_display(question)
        socketio.emit("play_audio", {
            "url": media_url,
            "start": media_start,
            "duration": question.duration,
            "id": question.id,
            "question_index": idx,
            "total_questions": total_songs,
            "artist": question_display.get("artist", ""),
            "title": question_display.get("title", ""),
            "round": round_num,
            "question_type": question.type,
            "question_text": question_display.get("question_text", ""),
            "extra_question": question_display.get("extra_question", ""),
        })

        # Send unlockInput with question type details
        unlock_payload = get_question_unlock_payload(question)
        unlock_payload["question_started_at"] = time.time()
        unlock_payload["question_duration"] = question.duration

        quiz_settings["current_question_id"] = question.id
        quiz_settings["current_question_started_at"] = unlock_payload["question_started_at"]
        quiz_settings["current_question_duration"] = question.duration
        quiz_settings["current_question_phase"] = "question"

        socketio.emit("player_unlock_input", unlock_payload)
        socketio.emit("tv_start_timer", {"seconds": question.duration, "round": round_num})

        # DINAMIČKO ČEKANJE (PJESMA)
        elapsed = 0
        while elapsed < question.duration:
            if not quiz_settings["quiz_paused"]:
                time.sleep(1)
                elapsed += 1
                # Slanje server-side timer update svakih sekundi
                remaining = question.duration - elapsed
                socketio.emit("timer_update", {
                    "remaining": remaining,
                    "total": question.duration,
                    "question_id": question.id
                })
            else:
                time.sleep(0.5) # Provjeravaj češće je li pauza gotova

        # 2. ZAKLJUČAJ I PRIKAŽI TOČAN ODGOVOR
        socketio.emit("player_lock_input")
        quiz_settings["current_question_phase"] = "answer"
        socketio.emit("round_locked", {"round": round_num})
        answer_key = get_question_answer_key(question)
        display_title = answer_key.get("title") or answer_key.get("choice") or ""
        socketio.emit("screen_show_correct", {
            "id": question.id,
            "artist": answer_key.get("artist", ""),
            "title": display_title,
            "round": round_num,
            "duration": 15
        })
        
        # 3. POZADINSKO BODOVANJE DOK TRAJE PAUZA
        answers_to_grade = Answer.query.filter_by(question_id=question_id).all()
        for ans in answers_to_grade:
            try:
                grade_answer_for_question(ans, question)
            except Exception as e:
                print(f"Warning: Failed to auto-grade answer {ans.id} for question {question_id}: {str(e)}")
        db.session.commit()

        # Osvježi ljestvicu uživo nakon svake pjesme
        calculate_and_broadcast_leaderboard()
        broadcast_grading_data()

        # Send individual grading to each player
        for ans in answers_to_grade:
            player_answer = {
                "artist": ans.artist_guess or "",
                "title": ans.title_guess or "",
                "extra": getattr(ans, 'extra_guess', '') or "",
                "choice": getattr(ans, 'choice_selected', -1) or -1
            }
            correct_answer = get_question_answer_key(question)
            # Get multiple choice options if applicable
            choices = []
            if question.type == "text_multiple" and question.text_multiple:
                choices = question.text_multiple.get_choices()

            socketio.emit("player_show_answer", {
                "player_answer": player_answer,
                "correct_answer": correct_answer,
                "artist_points": float(ans.artist_points or 0),
                "title_points": float(ans.title_points or 0),
                "extra_points": float(ans.extra_points or 0),
                "max_points": get_max_points(question),
                "choices": choices
            }, room=ans.player_name)

        # DINAMIČKO ČEKANJE (PRIKAZ ODGOVORA)
        elapsed = 0
        while elapsed < answer_display_seconds:
            if not quiz_settings["quiz_paused"]:
                time.sleep(1)
                elapsed += 1
                # Slanje server-side timer update svakih sekundi
                remaining = answer_display_seconds - elapsed
                socketio.emit("timer_update", {
                    "remaining": remaining,
                    "total": answer_display_seconds,
                    "question_id": question.id,
                    "phase": "answer_display"
                })
            else:
                time.sleep(0.5)

        # 4. SLJEDEĆA PJESMA ILI KRAJ RUNDE
        next_question = Question.query.filter(
            Question.quiz_id == question.quiz_id,
            Question.round_number == round_num,
            Question.position > question.position
        ).order_by(Question.position).first()

        if next_question:
            auto_quiz_sequence(next_question.id, round_num, app)
        else:
            quiz_settings["current_question_id"] = None
            quiz_settings["current_question_started_at"] = None
            quiz_settings["current_question_duration"] = None
            quiz_settings["current_question_phase"] = None
            # Round is finished - show summary
            finalize_round(round_num)

            # Get all songs in this round
            quiz = get_active_quiz()
            questions_in_round = Question.query.filter_by(
                quiz_id=quiz.id,
                round_number=round_num
            ).order_by(Question.position).all()

            # Prepare round summary data for TV screen
            round_summary = []
            for q in questions_in_round:
                answer_key = get_question_answer_key(q)
                display = get_question_display(q)
                artist_label = display.get("artist", "")
                title_label = display.get("title", "")
                if q.type in ["text", "text_multiple"]:
                    artist_label = ""
                    title_label = answer_key.get("title") or answer_key.get("choice") or ""
                elif q.type == "simultaneous":
                    artist_label = ""
                    title_label = answer_key.get("title", "")
                    extra = answer_key.get("extra") or ""
                    if extra:
                        title_label = f"{title_label} / {extra}"
                round_summary.append({
                    "artist": artist_label,
                    "title": title_label,
                    "question_position": display.get("order", 1)
                })

            # Emit to TV screen - show all correct answers
            socketio.emit("screen_show_round_summary", {
                "round": round_num,
                "songs": round_summary
            })

            # Emit to each player their final answers for the round
            all_players = Player.query.all()
            for player in all_players:
                player_answers = Answer.query.filter_by(player_name=player.name, round_number=round_num).all()
                player_round_answers = []
                for ans in player_answers:
                    q = Question.query.get(ans.question_id)
                    if q:
                        answer_key = get_question_answer_key(q)
                        display_title = answer_key.get("title") or answer_key.get("choice") or ""
                        player_round_answers.append({
                            "question_position": q.position or 1,
                            "artist_guess": ans.artist_guess or "",
                            "title_guess": ans.title_guess or "",
                            "extra_guess": ans.extra_guess or "",
                            "correct_artist": answer_key.get("artist", ""),
                            "correct_title": display_title,
                            "correct_extra": answer_key.get("extra", ""),
                            "artist_points": float(ans.artist_points or 0),
                            "title_points": float(ans.title_points or 0),
                            "extra_points": float(ans.extra_points or 0),
                            "max_points": get_max_points(q),
                            "question_type": q.type
                        })

                socketio.emit("player_show_round_summary", {
                    "round": round_num,
                    "answers": player_round_answers
                }, room=player.name)

            socketio.emit("admin_round_finished", {"round": round_num})

def auto_quiz_sequence_with_countdown(question_id, round_num, app, socketio_instance):
    """Wrapper for auto_quiz_sequence with 30-second pre-round countdown."""
    import time
    # Countdown already happening on frontend, wait for it to finish
    time.sleep(30)
    # Then start the quiz sequence
    auto_quiz_sequence(question_id, round_num, app)

# --- SOCKET EVENTS ---

def register_admin_events(socketio):
    @socketio.on("admin_start_auto_run")
    def handle_auto_run(data):
        emit("admin_auto_run_ack", {
            "status": "ok",
            "round": data.get("round", 1),
            "id": data.get("id")
        })
        app = current_app._get_current_object()
        round_num = data.get("round", 1)
        quiz_settings["quiz_started"] = True

        # Broadcast 30-second countdown before round starts
        socketio.emit("round_countdown_start", {"round": round_num})

        # Start quiz after 30 second countdown
        socketio.start_background_task(
            auto_quiz_sequence_with_countdown,
            data.get("id"),
            round_num,
            app,
            socketio
        )

    @socketio.on("admin_play_song")
    def handle_single_play(data):
        question = Question.query.get(data["id"])
        if not question:
            return
        idx = get_question_index(question)
        quiz_settings["quiz_started"] = True

        media = get_question_media(question)
        media_url = media.get("url", "")
        media_start = media.get("start", 0.0)
        unlock_payload = get_question_unlock_payload(question)
        unlock_payload["question_started_at"] = time.time()
        unlock_payload["question_duration"] = question.duration

        quiz_settings["current_question_id"] = question.id
        quiz_settings["current_question_started_at"] = unlock_payload["question_started_at"]
        quiz_settings["current_question_duration"] = question.duration
        quiz_settings["current_question_phase"] = "question"

        emit("play_audio", {
            "url": media_url,
            "start": media_start,
            "duration": question.duration,
            "id": question.id,
            "question_type": question.type,
            "question_index": idx,
            "round": question.round_number,
            "question_text": unlock_payload.get("question_text", ""),
            "extra_question": unlock_payload.get("extra_question", ""),
        })
        emit("player_unlock_input", unlock_payload)
        emit("tv_start_timer", {"seconds": question.duration, "round": question.round_number})

    @socketio.on("admin_toggle_pause")
    def handle_toggle_pause(data):
        # Atomska operacija - postavi novu vrijednost
        new_pause_state = data.get("paused", False)
        quiz_settings["quiz_paused"] = new_pause_state

        # Obavijesti sve (Admina, TV, Igrače) da je kviz pauziran/nastavljen
        socketio.emit("quiz_pause_state", {
            "paused": quiz_settings["quiz_paused"],
            "timestamp": time.time()  # Dodaj timestamp za sinkronizaciju
        })

    @socketio.on("admin_finalize_round")
    def handle_manual_finalize(data):
        round_num = data.get("round")
        finalize_round(round_num)

    @socketio.on("admin_live_arm")
    def handle_live_arm(data):
        armed = bool(data.get("armed"))
        if armed:
            live_armed_clients.add(request.sid)
        else:
            live_armed_clients.discard(request.sid)
        emit("admin_live_arm_ack", {"armed": armed})

    @socketio.on("disconnect")
    def handle_disconnect():
        live_armed_clients.discard(request.sid)

    @socketio.on("admin_get_grading_data")
    def handle_get_grading():
        broadcast_grading_data()

    @socketio.on("admin_request_grading")
    def handle_request_grading(data):
        """Šalje grading podatke filtirane po runди."""
        round_num = data.get("round", 1)
        quiz = get_active_quiz()
        if not quiz:
            return

        # Dohvati sve pjesme za ovu rundu i kviz
        questions = Question.query.filter_by(quiz_id=quiz.id, round_number=round_num).all()
        question_ids = [q.id for q in questions]

        # Dohvati sve odgovore za te pjesme
        answers = Answer.query.filter(Answer.question_id.in_(question_ids)).all()

        grading_payload = []
        question_map = {q.id: q for q in questions}
        for ans in answers:
            question = question_map.get(ans.question_id)
            grading_payload.append({
                "id": ans.id,
                "player_name": ans.player_name,
                "artist_guess": ans.artist_guess,
                "title_guess": ans.title_guess,
                "extra_guess": ans.extra_guess,
                "artist_points": float(ans.artist_points),
                "title_points": float(ans.title_points),
                "extra_points": float(ans.extra_points),
                "question_id": ans.question_id,
                "round_number": question.round_number if question else 0,
                "position": question.position if question else 0,
                "question_type": question.type if question else "",
            })

        # Šalje samo tražitelju (adminu)
        emit("admin_receive_grading_data", grading_payload)

    @socketio.on("admin_update_score")
    def handle_score_update(data):
        try:
            # Validacija ulaza
            answer_id = data.get("answer_id")
            score_type = data.get("type")
            score_value = float(data.get("value", -1))

            # Provjeri da je vrijednost validna (0, 0.5 ili 1.0)
            if score_value not in [0, 0.5, 1.0]:
                print(f"Invalid score value: {score_value}")
                return

            # Provjeri da je tip validna
            if score_type not in ["artist", "title", "extra"]:
                print(f"Invalid score type: {score_type}")
                return

            ans = Answer.query.get(answer_id)
            if not ans:
                print(f"Answer not found: {answer_id}")
                return

            if score_type == "artist":
                ans.artist_points = score_value
            elif score_type == "title":
                ans.title_points = score_value
            else:
                ans.extra_points = score_value

            db.session.commit()
            # Nakon ručne promjene bodova, odmah osvježi TV
            calculate_and_broadcast_leaderboard()
            broadcast_grading_data()
        except Exception as e:
            print(f"Error in handle_score_update: {str(e)}")

    @socketio.on("admin_delete_player")
    def handle_delete_player(data):
        player_name = data.get("player_name")
        player = Player.query.filter_by(name=player_name).first()
        if player:
            Answer.query.filter_by(player_name=player_name).delete()
            db.session.delete(player)
            db.session.commit()

            socketio.emit("admin_update_player_list", get_all_players_data())
            calculate_and_broadcast_leaderboard()

    @socketio.on("admin_lock_player")
    def handle_lock_player(data):
        """Zaključava igrača od daljnjeg unosa odgovora."""
        player_name = data.get("player_name")
        player = Player.query.filter_by(name=player_name).first()
        if player:
            # Označi sve buduće odgovore kao zaključane za tog igrača
            # Ili možeš dodati polje "locked" u Player model ako trebaš
            print(f"Player {player_name} locked for remainder of quiz")
            socketio.emit("admin_update_player_list", get_all_players_data())

    @socketio.on("admin_get_players")
    def handle_get_players():
        emit("admin_player_list_full", get_all_players_data())
        
    @socketio.on("screen_ready")
    def handle_screen_ready():
        calculate_and_broadcast_leaderboard()

    @socketio.on("admin_toggle_registrations")
    def handle_toggle_reg(data):
        quiz_settings["registrations_open"] = data.get("open", False)
        
        if quiz_settings["registrations_open"]:
            # Dohvati IP adresu servera za QR kod
            import socket
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            # Možeš i hardkodirati ako server ima fiksni IP
            url = f"http://{ip_address}:5000/player"
            
            socketio.emit("screen_show_welcome", {
                "message": "Molim da se spojite na Wi-Fi, prijavite na kviz i slobodno nešto popijete",
                "url": url
            })
        else:
            socketio.emit("screen_hide_welcome")