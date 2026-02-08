from extensions import db


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    round_number = db.Column(db.Integer, default=1)
    position = db.Column(db.Integer, default=0)
    type = db.Column(db.String(20), default="audio")
    duration = db.Column(db.Float, default=30.0)

    song = db.relationship("Song", uselist=False, back_populates="question", cascade="all, delete-orphan")
    video = db.relationship("Video", uselist=False, back_populates="question", cascade="all, delete-orphan")
    text = db.relationship("TextQuestion", uselist=False, back_populates="question", cascade="all, delete-orphan")
    text_multiple = db.relationship("TextMultiple", uselist=False, back_populates="question", cascade="all, delete-orphan")
    simultaneous = db.relationship("SimultaneousQuestion", uselist=False, back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("quiz_id", "round_number", "position", name="uq_question_quiz_round_position"),
        db.Index("ix_question_quiz", "quiz_id"),
        db.Index("ix_question_round", "round_number"),
    )
