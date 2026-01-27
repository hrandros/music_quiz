from extensions import db, socketio
from flask_socketio import emit
from flask import current_app, url_for
from musicquiz.models import Player, Song, Answer
from musicquiz.services.quiz_service import get_active_quiz
from musicquiz.services.player_status import get_all_players_data
from musicquiz.services.grading_service import auto_grade_answer
import time

# Globalno stanje kviza
quiz_settings = {
    "registrations_open": False,
    "quiz_paused": False
}

# --- POMOĆNE FUNKCIJE ---

def get_song_index(song):
    """Vraća redni broj pjesme unutar runde."""
    songs = Song.query.filter_by(quiz_id=song.quiz_id, round_number=song.round_number).order_by(Song.id).all()
    return next((i + 1 for i, s in enumerate(songs) if s.id == song.id), 1)

def calculate_and_broadcast_leaderboard():
    """Centralna funkcija za izračun bodova i slanje ljestvice na TV."""
    all_players = Player.query.all()
    leaderboard = {}
    
    # Prvo ažuriramo bazu za svakog igrača
    for p in all_players:
        # Sumiramo sve bodove iz tablice Answer za tog igrača
        pts = db.session.query(db.func.sum(Answer.artist_points + Answer.title_points))\
                .filter(Answer.player_name == p.name).scalar() or 0
        p.score = float(pts)
        leaderboard[p.name] = p.score
    
    db.session.commit()
    socketio.emit("update_leaderboard", leaderboard)
    return leaderboard

def finalize_round(round_num):
    """Završni auto-grade za cijelu rundu i finalno slanje ljestvice."""
    quiz = get_active_quiz()
    songs = Song.query.filter_by(quiz_id=quiz.id, round_number=round_num).all()
    song_map = {s.id: s for s in songs}

    answers = Answer.query.filter_by(round_number=round_num).all()
    for ans in answers:
        if ans.song_id in song_map:
            try:
                auto_grade_answer(ans, song_map[ans.song_id])
            except: pass
    
    db.session.commit()
    calculate_and_broadcast_leaderboard()

# --- GLAVNA LOGIKA KVIZA ---

def auto_quiz_sequence(song_id, round_num, app):
    """Automatska petlja: Pjesma -> Lock -> Rezultat -> Bodovanje -> Next."""
    with app.app_context():
        song = Song.query.get(song_id)
        if not song: return

        idx = get_song_index(song)
        audio_url = f"/stream_song/{song.filename}"

        total_songs = Song.query.filter_by(
            quiz_id=song.quiz_id, 
            round_number=round_num
        ).count()
        
        # 1. EMITIRAJ POČETAK PJESME
        socketio.emit("play_audio", {
            "url": audio_url,
            "start": song.start_time,
            "duration": song.duration,
            "id": song.id,
            "song_index": idx,
            "total_songs": total_songs,
            "artist": song.artist,
            "title": song.title,
            "round": round_num
        })
        socketio.emit("player_unlock_input", {"song_id": song.id, "song_index": idx, "round": round_num})
        socketio.emit("tv_start_timer", {"seconds": song.duration, "round": round_num})

        # DINAMIČKO ČEKANJE (PJESMA)
        elapsed = 0
        while elapsed < song.duration:
            if not quiz_settings["quiz_paused"]:
                time.sleep(1)
                elapsed += 1
            else:
                time.sleep(0.5) # Provjeravaj češće je li pauza gotova

        # 2. ZAKLJUČAJ I PRIKAŽI TOČAN ODGOVOR
        socketio.emit("player_lock_input")
        socketio.emit("round_locked", {"round": round_num})
        socketio.emit("screen_show_correct", {
            "artist": song.artist,
            "title": song.title,
            "round": round_num,
            "duration": 15
        })
        
        # 3. POZADINSKO BODOVANJE DOK TRAJE PAUZA
        answers_to_grade = Answer.query.filter_by(song_id=song_id).all()
        for ans in answers_to_grade:
            try: auto_grade_answer(ans, song)
            except: pass
        db.session.commit()
        
        # Osvježi ljestvicu uživo nakon svake pjesme
        calculate_and_broadcast_leaderboard()

        # DINAMIČKO ČEKANJE (PJESMA)
        elapsed = 0
        while elapsed < song.duration:
            if not quiz_settings["quiz_paused"]:
                time.sleep(1)
                elapsed += 1
            else:
                time.sleep(0.5)

        # 4. SLJEDEĆA PJESMA ILI KRAJ RUNDE
        next_song = Song.query.filter(
            Song.quiz_id == song.quiz_id,
            Song.round_number == round_num,
            Song.id > song.id
        ).order_by(Song.id).first()

        if next_song:
            auto_quiz_sequence(next_song.id, round_num, app)
        else:
            finalize_round(round_num)
            socketio.emit("admin_round_finished", {"round": round_num})

# --- SOCKET EVENTS ---

def register_admin_events(socketio):
    
    @socketio.on("admin_start_auto_run")
    def handle_auto_run(data):
        app = current_app._get_current_object()
        socketio.start_background_task(auto_quiz_sequence, data.get("id"), data.get("round"), app)

    @socketio.on("admin_play_song")
    def handle_single_play(data):
        s = Song.query.get(data["id"])
        if not s: return
        idx = get_song_index(s)
        payload = {"song_id": s.id, "song_index": idx, "round": s.round_number}
        
        emit("play_audio", {"url": f"/stream_song/{s.filename}", "start": s.start_time, "duration": s.duration, "id": s.id}, broadcast=True)
        emit("player_unlock_input", payload, broadcast=True)
        emit("tv_start_timer", {"seconds": s.duration, "round": s.round_number}, broadcast=True)

    @socketio.on("admin_toggle_pause")
    def handle_toggle_pause(data):
        quiz_settings["quiz_paused"] = data.get("paused", False)
        # Obavijesti sve (Admina, TV, Igrače) da je kviz pauziran/nastavljen
        socketio.emit("quiz_pause_state", {"paused": quiz_settings["quiz_paused"]})

    @socketio.on("admin_finalize_round")
    def handle_manual_finalize(data):
        round_num = data.get("round")
        finalize_round(round_num)
        
        quiz = get_active_quiz()
        songs = Song.query.filter_by(quiz_id=quiz.id, round_number=round_num).all()
        answers_data = [{"artist": s.artist, "title": s.title} for s in songs]
        emit("screen_show_answers", {"answers": answers_data, "duration": 15}, broadcast=True)

    @socketio.on("admin_update_score")
    def handle_score_update(data):
        ans = Answer.query.get(data["answer_id"])
        if ans:
            if data["type"] == "artist": ans.artist_points = float(data["value"])
            else: ans.title_points = float(data["value"])
            db.session.commit()
            # Nakon ručne promjene bodova, odmah osvježi TV
            calculate_and_broadcast_leaderboard()

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