from extensions import db
from flask_socketio import emit, join_room
from musicquiz.models import Player, Answer, Song
from flask import request

def register_player_events(socketio):

    # ---------------------------
    # PLAYER JOIN
    # ---------------------------
    @socketio.on("player_join")
    def handle_join(data):
        name = data["name"]
        pin = data.get("pin", "0000")

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

        # Update admin
        from musicquiz.services.player_status import get_all_players_data
        emit("admin_update_player_list", get_all_players_data(), broadcast=True)

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
            {"name": name, "status": status},
            broadcast=True
        )

    # ---------------------------
    # PLAYER SUBMIT ANSWER
    # ---------------------------
    @socketio.on("player_submit_answer")
    def handle_player_answer(data):
        player_name = data["player_name"]
        song_id = data["song_id"]

        ans = Answer.query.filter_by(
            player_name=player_name,
            song_id=song_id
        ).first()

        if not ans:
            # Create new one
            ans = Answer(
                player_name=player_name,
                song_id=song_id
            )
            song = Song.query.get(song_id)
            if song:
                ans.round_number = song.round_number
            db.session.add(ans)

        # Update fields
        ans.artist_guess = data.get("artist", "")
        ans.title_guess = data.get("title", "")

        db.session.commit()