from extensions import db

class Answer(db.Model):
    """
    Answer submission model supporting multiple question types.
    Supports:
    - Text answers (artist/title for audio, or general text)
    - Multiple choice (choice selection)
    - Extra field (third answer field for simultaneous questions)
    """
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100), db.ForeignKey('player.name', ondelete='CASCADE'), nullable=False)
    round_number = db.Column(db.Integer)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id", ondelete="CASCADE"), nullable=False)

    # Text answers (for audio, video, text questions)
    artist_guess = db.Column(db.String(200), default="")  # 1st field (artist/topic)
    title_guess = db.Column(db.String(200), default="")   # 2nd field (title/answer)
    extra_guess = db.Column(db.String(200), default="")   # 3rd field (extra text for simultaneous)

    # Multiple choice answer
    choice_selected = db.Column(db.Integer, default=-1)   # Index of selected choice (-1 = no selection)

    # Scoring
    artist_points = db.Column(db.Float, default=0.0)      # Points for field 1
    title_points = db.Column(db.Float, default=0.0)       # Points for field 2
    extra_points = db.Column(db.Float, default=0.0)       # Points for field 3

    # Timing
    is_locked = db.Column(db.Boolean, default=False)      # Whether answer is final
    submission_time = db.Column(db.Float, default=0.0)    # Seconds into the question when submitted
    timestamp = db.Column(db.DateTime, server_default=db.func.now())  # Database timestamp

    __table_args__ = (
        db.UniqueConstraint("player_name", "question_id", name="uq_answer_player_question"),
        db.Index("ix_answer_round", "round_number"),
        db.Index("ix_answer_question", "question_id"),
        db.Index("ix_answer_player", "player_name"),
    )

