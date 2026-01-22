from extensions import db

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100))
    round_number = db.Column(db.Integer)
    song_id = db.Column(db.Integer)
    artist_guess = db.Column(db.String(200), default="")
    title_guess = db.Column(db.String(200), default="")
    extra_guess = db.Column(db.String(200), default="")
    artist_points = db.Column(db.Float, default=0.0)
    title_points = db.Column(db.Float, default=0.0)
    extra_points = db.Column(db.Float, default=0.0)
    is_locked = db.Column(db.Boolean, default=False)