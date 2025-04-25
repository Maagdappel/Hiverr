from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hiverr.db'
db = SQLAlchemy(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/apiaries")
def list_apiaries():
    apiaries = Apiary.query.all()
    return "<br>".join([f"{a.id}: {a.name} - {a.location}" for a in apiaries])

@app.route("/add-apiary")
def add_apiary():
    new = Apiary(name="Backyard Hive", location="Behind the shed", notes="Sunny spot")
    db.session.add(new)
    db.session.commit()
    return "Apiary added!"


class Apiary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Apiary {self.name}>'


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
