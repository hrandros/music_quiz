from flask import Flask
import atexit
from config import Config
from extensions import db, socketio
from musicquiz.routes import register_routes
from musicquiz.sockets import register_sockets
from musicquiz import models as models_module
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
    with app.app_context():
        _ = models_module.__name__
        db.create_all()
        print("Baza podataka i tablice su uspješno kreirani!")
    register_routes(app)
    register_sockets(socketio)
    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        try:
            from musicquiz.models import LogEntry

            db.session.add(LogEntry(source="server", message="server_start"))
            db.session.commit()
        except Exception:
            pass

    def _log_server_stop():
        with app.app_context():
            try:
                from musicquiz.models import LogEntry

                db.session.add(LogEntry(source="server", message="server_stop"))
                db.session.commit()
            except Exception:
                pass
        print("server_stop", flush=True)

    atexit.register(_log_server_stop)
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    host = os.getenv("MQ_HOST", "0.0.0.0")
    port = int(os.getenv("MQ_PORT", "5000"))
    debug = os.getenv("MQ_DEBUG", "0").lower() in {"1", "true", "yes"}
    print(f"ROCK QUIZ READY ON http://{ip}:{port}", flush=True)
    print("server_start", flush=True)
    socketio.run(app, host=host, port=port, debug=debug)
