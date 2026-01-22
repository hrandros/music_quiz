from flask import Flask
from config import Config
from extensions import db, socketio
from musicquiz.routes import register_routes
from musicquiz.sockets import register_sockets
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "musicquiz", "templates"),
        static_folder=os.path.join(BASE_DIR, "musicquiz", "static")
    )
    app.config.from_object(Config)
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")
    register_routes(app)
    register_sockets(socketio)
    return app


if __name__ == "__main__":
    app = create_app()
    # DEBUG ispisi — privremeno
    print("TEMPLATE FOLDER:", app.template_folder)
    print("STATIC FOLDER  :", app.static_folder)
    print("URL MAP:")
    for r in app.url_map.iter_rules():
        print(f"- {r.endpoint:20s} -> {r.rule}")
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    print(f"ROCK QUIZ READY ON http://{ip}:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
