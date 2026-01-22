from extensions import db
import datetime

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_created = db.Column(
        db.String(20),
        default=datetime.date.today().strftime("%Y-%m-%d"))
    is_active = db.Column(db.Boolean, default=False)