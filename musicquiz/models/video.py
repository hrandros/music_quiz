from extensions import db


class Video(db.Model):
    """Video question details (linked to Question)."""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, unique=True)

    filename = db.Column(db.String(300), nullable=False)
    artist = db.Column(db.String(100), default="?")
    title = db.Column(db.String(100), default="?")
    start_time = db.Column(db.Float, default=0.0)

    question = db.relationship("Question", back_populates="video")

    __table_args__ = (
        db.Index("ix_video_question", "question_id"),
    )
