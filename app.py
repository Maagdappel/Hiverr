from flask import Flask, render_template
from flask import request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hiverr.db'
db = SQLAlchemy(app)

@app.route('/')
def index():
    return render_template('index.html', active_page='dashboard')

@app.route('/apiaries')
def apiaries():
    apiaries = Apiary.query.all()  # Retrieve all apiaries from the database
    return render_template('apiaries.html', apiaries=apiaries, active_page='apiaries')

@app.route('/edit-apiary/<int:id>', methods=['GET', 'POST'])
def edit_apiary(id):
    apiary = Apiary.query.get(id)  # Fetch the apiary by ID

    if request.method == 'POST':
        # Update the apiary with form data
        apiary.name = request.form['name']
        apiary.location = request.form['location']
        db.session.commit()  # Commit changes to the database
        flash(f"Apiary: {apiary.name} edited successfully!", "success")

        return redirect(url_for('apiaries'))  # Redirect to the apiaries list

    return render_template('edit_apiary.html', apiary=apiary)

@app.route('/delete-apiary/<int:id>', methods=['GET'])
def delete_apiary(id):
    apiary = Apiary.query.get(id)  # Fetch the apiary by ID
    db.session.delete(apiary)  # Delete it from the session
    db.session.commit()  # Commit the changes to the database
    flash(f"Apiary: {apiary.name} deleted successfully!", "success")
    return redirect(url_for('apiaries'))  # Redirect back to the apiaries list


@app.route('/add-apiary', methods=['GET', 'POST'])
def add_apiary():
    if request.method == 'POST':
        # Get data from the form
        name = request.form['name']
        location = request.form['location']

        # Create a new Apiary object
        new_apiary = Apiary(name=name, location=location)

        # Add to the database
        db.session.add(new_apiary)
        db.session.commit()
        flash(f"Apiary: {new_apiary.name} added successfully!", "success")

        # Redirect to the apiaries list
        return redirect(url_for('apiaries'))

    return render_template('add_apiary.html')

@app.route('/hives')
def hives():
    hives = Hive.query.all()  # Retrieve all Hives from the database
    return render_template('hives.html', hives=hives, active_page='hives')

@app.route('/add-hive', methods=['GET', 'POST'])
def add_hive():
    apiaries = Apiary.query.all()
    if request.method == 'POST':
        if not apiaries:
            flash("You must create an apiary first before adding a hive.", "danger")
            return redirect(url_for('apiaries'))
        # Get data from the form
        name = request.form['name']
        apiary_id = request.form['apiary_id']

        # Create a new Hive object
        new_hive = Hive(name=name, apiary_id=apiary_id)

        # Add to the database
        db.session.add(new_hive)
        db.session.commit()
        flash(f"Hive: {new_hive.name} added successfully!", "success")

        # Redirect to the hives list
        return redirect(url_for('hives'))

    return render_template('add_hive.html', apiaries=apiaries)

@app.route('/edit-hive/<int:id>', methods=['GET', 'POST'])
def edit_hive(id):
    hive = Hive.query.get(id)  # Fetch the hive by ID
    apiaries = Apiary.query.all() # Get all apiaries

    if request.method == 'POST':
        # Update the hive with form data
        hive.name = request.form['name']
        hive.apiary_id = request.form['apiary_id']
        db.session.commit()  # Commit changes to the database
        flash(f"Hive: {hive.name} edited successfully!", "success")

        return redirect(url_for('hives'))  # Redirect to the apiaries list

    return render_template('edit_hive.html', hive=hive, apiaries=apiaries)

@app.route('/delete-hive/<int:id>', methods=['GET'])
def delete_hive(id):
    hive = Hive.query.get(id)  # Fetch the hive by ID
    db.session.delete(hive)  # Delete it from the session
    db.session.commit()  # Commit the changes to the database
    flash(f"Hive: {hive.name} deleted successfully!", "success")
    return redirect(url_for('hives'))  # Redirect back to the hives list

@app.route('/queens')
def queens():
    queens = Queen.query.all()  # Retrieve all queens from the database
    return render_template('queens.html', queens=queens, active_page='queens')

@app.route('/add-queen', methods=['GET', 'POST'])
def add_queen():
    hives = [hive for hive in Hive.query.all() if not hive.queens]
    if request.method == 'POST':
        if not hives:
            flash("You must create a hive first before adding a queen.", "danger")
            return redirect(url_for('hives'))
        # Get data from the form
        name = request.form['name']
        breeder = request.form['breeder']
        birth_date = datetime.strptime(request.form['birth_date'], '%Y-%m-%d')
        #hive_id = request.form['hive_id']
        hive_id = request.form.get('hive_id')
        if not hive_id:
            flash("You must assign the queen to a hive.", "error")
            return redirect(request.url)  # or re-render the template with current data

        # Create a new Queen object
        new_queen = Queen(name=name, breeder=breeder, birth_date=birth_date, hive_id=hive_id)

        # Add to the database
        db.session.add(new_queen)
        db.session.commit()
        flash(f"Queen: {new_queen.name} added successfully!", "success")

        # Redirect to the hives list
        return redirect(url_for('queens'))

    
    return render_template('add_queen.html', hives=hives)

@app.route('/edit-queen/<int:id>', methods=['GET', 'POST'])
def edit_queen(id):
    queen = Queen.query.get(id)  # Fetch the Queen by ID

    # Find hives where no queen is currently assigned, include the current hive
    hives = Hive.query.filter(~Hive.queens.any()).all()
    if queen.hive and queen.hive not in hives:
        hives.append(queen.hive)

    if request.method == 'POST':
        # Update queen details from form
        queen.name = request.form['name']
        queen.breeder = request.form['breeder']
        queen.birth_date = datetime.strptime(request.form['birth_date'], '%Y-%m-%d')

        # Handle hive assignment (or keep the current hive if no new hive selected)
        hive_id = request.form.get('hive_id')

        # If a new hive is selected and it's different, assign it to the queen
        if hive_id:
            queen.hive_id = hive_id
        elif not hive_id and queen.hive_id is not None:
            # If no hive is selected and the queen already has a hive, keep the current hive
            pass
        else:
            # If no hive is selected and the queen doesn't have a hive, assign her to "No Hive"
            queen.hive_id = None

        # Commit changes to the database
        db.session.commit()
        flash(f"Queen: {queen.name} edited successfully!", "success")

        # Redirect to queens list
        return redirect(url_for('queens'))

    return render_template('edit_queen.html', queen=queen, hives=hives)

@app.route('/delete-queen/<int:id>', methods=['GET'])
def delete_queen(id):
    queen = Queen.query.get(id)  # Fetch the queen by ID
    db.session.delete(queen)  # Delete it from the session
    db.session.commit()  # Commit the changes to the database
    flash(f"Queen: {queen.name} deleted successfully!", "success")
    return redirect(url_for('queens'))  # Redirect back to the queens list

class Apiary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))

    hives = db.relationship('Hive', backref='apiary', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Apiary {self.name}>'

class Hive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    apiary_id = db.Column(db.Integer, db.ForeignKey('apiary.id'))

    queens = db.relationship('Queen', backref='hive', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Hive {self.name}>'
    
class Queen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    breeder = db.Column(db.String(100))
    birth_date = db.Column(db.Date)
    hive_id = db.Column(db.Integer, db.ForeignKey('hive.id'))

    def __repr__(self):
        return f'<Queen {self.name}>'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
