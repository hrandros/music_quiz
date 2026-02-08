import json
from extensions import db


class TextMultiple(db.Model):
    """Multiple choice question details (linked to Question)."""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, unique=True)

    question_text = db.Column(db.String(500), default="")
    choices = db.Column(db.String(2000), default="")
    correct_index = db.Column(db.Integer, default=0)

    question = db.relationship("Question", back_populates="text_multiple")

    __table_args__ = (
        db.Index("ix_text_multiple_question", "question_id"),
    )

    def get_choices(self):
        try:
            return json.loads(self.choices) if self.choices else []
        except Exception:
            return []

    def set_choices(self, choices):
        self.choices = json.dumps(choices) if choices else "[]"
