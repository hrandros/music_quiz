from extensions import db


class SimultaneousQuestion(db.Model):
    """Simultaneous (audio + text) question details (linked to Question)."""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, unique=True)

    filename = db.Column(db.String(300), nullable=False)
    artist = db.Column(db.String(100), default="?")
    title = db.Column(db.String(100), default="?")
    start_time = db.Column(db.Float, default=0.0)
    extra_question = db.Column(db.String(500), default="")
    extra_answer = db.Column(db.String(500), default="")

    question = db.relationship("Question", back_populates="simultaneous")

    __table_args__ = (
        db.Index("ix_simultaneous_question", "question_id"),
    )
