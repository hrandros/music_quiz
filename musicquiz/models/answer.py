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

__table_args__ = (
    db.UniqueConstraint("player_name", "song_id", name="uq_answer_player_song"),
    db.Index("ix_answer_round", "round_number"),
    db.Index("ix_answer_song", "song_id"),
    db.Index("ix_answer_player", "player_name"),
)
