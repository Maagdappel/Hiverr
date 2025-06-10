from flask import Flask, render_template
from flask import request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from zoneinfo import available_timezones
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hiverr.db'
db = SQLAlchemy(app)
@app.before_request
def require_login():
    allowed_endpoints = {'login', 'register', 'static'}
    if request.endpoint and request.endpoint not in allowed_endpoints and 'user_id' not in session:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('User created, please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

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

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password:
            flash('Password cannot be empty', 'danger')
            return redirect(url_for('change_password'))
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('change_password'))
        user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully', 'success')
        return redirect(url_for('settings'))
    return render_template('change_password.html', active_page='settings')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user = User.query.get(session['user_id'])
    tz_list = sorted(available_timezones())
    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.timezone = request.form.get('timezone')
        user.temperature_unit = request.form.get('temperature_unit')
        user.weight_unit = request.form.get('weight_unit')

        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
                filename = secure_filename(file.filename)
                path = os.path.join('static', 'uploads', filename)
                file.save(path)
                user.profile_picture = path

        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', user=user, timezones=tz_list, active_page='settings')

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

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    timezone = db.Column(db.String(50))
    temperature_unit = db.Column(db.String(10))
    weight_unit = db.Column(db.String(10))
    profile_picture = db.Column(db.String(200))
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@app.context_processor
def inject_sidebar_apiaries():
    return {'sidebar_apiaries': Apiary.query.all()}


@app.context_processor
def inject_current_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return {'current_user': user}
    return {}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=80)
