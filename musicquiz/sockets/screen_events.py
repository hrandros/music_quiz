from flask_socketio import emit
from extensions import socketio
from musicquiz.models import Player

@socketio.on("screen_ready")
def handle_screen_ready():
    # Dohvati sve igrače i pošalji njihove trenutne bodove (na početku 0)
    players = Player.query.order_by(Player.name).all()
    leaderboard = {p.name: p.score for p in players}
    emit("update_leaderboard", leaderboard)

def register_screen_events(socketio):
    # Screen ne šalje ništa, samo prima eventove
    pass