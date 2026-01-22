from .admin_events import register_admin_events
from .player_events import register_player_events
from .screen_events import register_screen_events

def register_sockets(socketio):
    register_admin_events(socketio)
    register_player_events(socketio)
    register_screen_events(socketio)