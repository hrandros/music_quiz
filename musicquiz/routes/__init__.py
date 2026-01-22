from .admin_routes import admin_bp
from .public_routes import public_bp
from .screen_routes import screen_bp
from .file_routes import file_bp

def register_routes(app):
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(screen_bp)
    app.register_blueprint(file_bp)