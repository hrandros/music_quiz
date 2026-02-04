from extensions import db
import datetime

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.Date, default=datetime.date.today)    
    date_created = db.Column(db.DateTime, server_default=db.func.now())
    is_active = db.Column(db.Boolean, default=False)