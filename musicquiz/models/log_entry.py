from datetime import datetime, timedelta

from extensions import db


class LogEntry(db.Model):
    __tablename__ = "log_entries"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(hours=1)
    )
    source = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
