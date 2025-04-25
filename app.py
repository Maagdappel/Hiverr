from flask import Flask, render_template
from flask import request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hiverr.db'
db = SQLAlchemy(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/apiaries')
def apiaries():
    apiaries = Apiary.query.all()  # Retrieve all apiaries from the database
    return render_template('apiaries.html', apiaries=apiaries)

@app.route('/edit-apiary/<int:id>', methods=['GET', 'POST'])
def edit_apiary(id):
    apiary = Apiary.query.get(id)  # Fetch the apiary by ID

    if request.method == 'POST':
        # Update the apiary with form data
        apiary.name = request.form['name']
        apiary.location = request.form['location']
        apiary.notes = request.form['notes']
        db.session.commit()  # Commit changes to the database

        return redirect(url_for('apiaries'))  # Redirect to the apiaries list

    return render_template('edit_apiary.html', apiary=apiary)

@app.route('/delete-apiary/<int:id>', methods=['GET'])
def delete_apiary(id):
    apiary = Apiary.query.get(id)  # Fetch the apiary by ID
    db.session.delete(apiary)  # Delete it from the session
    db.session.commit()  # Commit the changes to the database
    return redirect(url_for('apiaries'))  # Redirect back to the apiaries list


@app.route('/add-apiary', methods=['GET', 'POST'])
def add_apiary():
    if request.method == 'POST':
        # Get data from the form
        name = request.form['name']
        location = request.form['location']
        notes = request.form['notes']

        # Create a new Apiary object
        new_apiary = Apiary(name=name, location=location, notes=notes)

        # Add to the database
        db.session.add(new_apiary)
        db.session.commit()

        # Redirect to the apiaries list
        return redirect(url_for('apiaries'))

    return render_template('add_apiary.html')


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
