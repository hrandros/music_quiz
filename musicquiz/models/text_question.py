from extensions import db


class TextQuestion(db.Model):
    """Text question details (linked to Question)."""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, unique=True)

    question_text = db.Column(db.String(500), default="")
    answer_text = db.Column(db.String(500), default="")

    question = db.relationship("Question", back_populates="text")

    __table_args__ = (
        db.Index("ix_text_question", "question_id"),
    )
