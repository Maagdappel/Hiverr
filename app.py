from flask import Flask, render_template, jsonify
from flask import request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from zoneinfo import available_timezones
from functools import wraps
import os
import base64
import hmac
import hashlib
import struct
import time
from io import BytesIO
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hiverr.db'
db = SQLAlchemy(app)


def generate_totp_secret():
    return base64.b32encode(os.urandom(10)).decode('utf-8')


def totp_now(secret, interval=30, digits=6):
    key = base64.b32decode(secret, True)
    counter = int(time.time()) // interval
    msg = struct.pack('>Q', counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0xf
    code = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp(secret, token):
    for drift in (-1, 0, 1):
        key = base64.b32decode(secret, True)
        counter = int((time.time() + drift * 30) // 30)
        msg = struct.pack('>Q', counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0xf
        code = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
        expected = str(code % (10 ** 6)).zfill(6)
        if token == expected:
            return True
    return False


def password_valid(password: str) -> bool:
    """Check password strength: 8+ chars, lower, upper and special."""
    if len(password) < 8:
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[^a-zA-Z0-9]', password):
        return False
    return True


def registration_enabled() -> bool:
    cfg = db.session.get(Config, 'registration_enabled')
    return bool(cfg and cfg.value == '1')
@app.before_request
def require_login():
    if User.query.count() == 0:
        allowed = {'static', 'setup_admin', 'setup_admin_verify_2fa'}
        if request.endpoint not in allowed:
            return redirect(url_for('setup_admin'))
    else:
        allowed_endpoints = {
            'login', 'register', 'static', 'two_factor',
            'setup_admin', 'setup_admin_verify_2fa', 'setup_apiary'
        }
        if request.endpoint and request.endpoint not in allowed_endpoints and 'user_id' not in session:
            return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.two_factor_secret:
                session['pending_user_id'] = user.id
                return redirect(url_for('two_factor'))
            session['user_id'] = user.id
            session['username'] = user.username
            if user.must_change_password:
                flash('Please change your password', 'info')
                return redirect(url_for('change_password'))
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/two-factor', methods=['GET', 'POST'])
def two_factor():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = db.session.get(User, user_id)
    if request.method == 'POST':
        token = request.form.get('token')
        if verify_totp(user.two_factor_secret, token):
            session.pop('pending_user_id')
            session['user_id'] = user.id
            session['username'] = user.username
            if user.must_change_password:
                flash('Please change your password', 'info')
                return redirect(url_for('change_password'))
            return redirect(url_for('index'))
        flash('Invalid authentication code', 'danger')
    return render_template('two_factor.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if not registration_enabled():
        flash('Registration is closed.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not password_valid(password):
            flash('Password must be at least 8 characters long and include upper, lower and special characters.', 'danger')
            return redirect(url_for('register'))
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


@app.route('/setup-admin', methods=['GET', 'POST'])
def setup_admin():
    if User.query.count() > 0:
        return redirect(url_for('login'))

    secret = session.get('setup_2fa_secret')
    if not secret:
        secret = generate_totp_secret()
        session['setup_2fa_secret'] = secret

    qr_data = None
    try:
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
        from qrcode.image.styles.colormasks import RadialGradiantColorMask

        otpauth = f"otpauth://totp/Hiverr:admin?secret={secret}&issuer=Hiverr"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=8, border=1)
        qr.add_data(otpauth)
        qr.make(fit=True)
        img = qr.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer(), color_mask=RadialGradiantColorMask())
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    except ModuleNotFoundError:
        pass

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        full_name = request.form.get('full_name')
        email = request.form.get('email') or None
        enable2fa = request.form.get('enable2fa')
        token = request.form.get('token')

        if not password_valid(password):
            flash('Password must be at least 8 characters long and include upper, lower and special characters.', 'danger')
            return render_template('setup_admin.html', secret=secret, qr_data=qr_data)
        if password != confirm:
            flash('Passwords do not match', 'danger')
            return render_template('setup_admin.html', secret=secret, qr_data=qr_data)

        user = User(username=username, full_name=full_name, email=email, role='admin')
        user.set_password(password)

        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
                filename = secure_filename(file.filename)
                path = os.path.join('static', 'uploads', filename)
                file.save(path)
                user.profile_picture = path

        if enable2fa:
            if session.get('twofa_verified') or (token and verify_totp(secret, token)):
                user.two_factor_secret = secret
            else:
                flash('Invalid authentication code', 'danger')
                return render_template('setup_admin.html', secret=secret, qr_data=qr_data)

        db.session.add(user)
        db.session.commit()
        session.pop('setup_2fa_secret', None)
        session.pop('twofa_verified', None)
        flash('Administrator account created', 'success')
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('setup_apiary'))

    return render_template('setup_admin.html', secret=secret, qr_data=qr_data)


@app.route('/setup-admin/verify-2fa', methods=['POST'])
def setup_admin_verify_2fa():
    if User.query.count() > 0:
        return jsonify({'error': 'closed'}), 400

    secret = session.get('setup_2fa_secret')
    token = request.form.get('token')
    if not secret or not token:
        return jsonify({'error': 'missing'}), 400
    if verify_totp(secret, token):
        session['twofa_verified'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'invalid'}), 400


@app.route('/setup-apiary', methods=['GET', 'POST'])
def setup_apiary():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        apiary_name = request.form.get('apiary_name')
        hive_name = request.form.get('hive_name')
        queen_name = request.form.get('queen_name')

        apiary = None
        if apiary_name:
            apiary = Apiary(name=apiary_name, user_id=session['user_id'])
            db.session.add(apiary)

        hive = None
        if hive_name and apiary:
            hive = Hive(name=hive_name, apiary=apiary, user_id=session['user_id'])
            db.session.add(hive)

        if queen_name and hive:
            queen = Queen(name=queen_name, hive=hive, user_id=session['user_id'])
            db.session.add(queen)

        db.session.commit()
        flash('Setup complete!', 'success')
        return redirect(url_for('index'))

    return render_template('setup_apiary.html')

@app.route('/')
def index():
    return render_template('index.html', active_page='dashboard')

@app.route('/apiaries')
def apiaries():
    apiaries = Apiary.query.filter_by(user_id=session['user_id']).all()
    return render_template('apiaries.html', apiaries=apiaries, active_page='apiaries')

@app.route('/edit-apiary/<int:id>', methods=['GET', 'POST'])
def edit_apiary(id):
    apiary = db.session.get(Apiary, id)  # Fetch the apiary by ID
    if apiary.user_id != session['user_id']:
        abort(403)

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
    apiary = db.session.get(Apiary, id)
    if apiary.user_id != session['user_id']:
        abort(403)
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
        new_apiary = Apiary(name=name, location=location, user_id=session['user_id'])

        # Add to the database
        db.session.add(new_apiary)
        db.session.commit()
        flash(f"Apiary: {new_apiary.name} added successfully!", "success")

        # Redirect to the apiaries list
        return redirect(url_for('apiaries'))

    return render_template('add_apiary.html')

@app.route('/hives')
def hives():
    hives = Hive.query.filter_by(user_id=session['user_id']).all()
    return render_template('hives.html', hives=hives, active_page='hives')

@app.route('/add-hive', methods=['GET', 'POST'])
def add_hive():
    apiaries = Apiary.query.filter_by(user_id=session['user_id']).all()
    if request.method == 'POST':
        if not apiaries:
            flash("You must create an apiary first before adding a hive.", "danger")
            return redirect(url_for('apiaries'))
        # Get data from the form
        name = request.form['name']
        apiary_id = request.form['apiary_id']

        # Create a new Hive object
        new_hive = Hive(name=name, apiary_id=apiary_id, user_id=session['user_id'])

        # Add to the database
        db.session.add(new_hive)
        db.session.commit()
        flash(f"Hive: {new_hive.name} added successfully!", "success")

        # Redirect to the hives list
        return redirect(url_for('hives'))

    return render_template('add_hive.html', apiaries=apiaries)

@app.route('/edit-hive/<int:id>', methods=['GET', 'POST'])
def edit_hive(id):
    hive = db.session.get(Hive, id)  # Fetch the hive by ID
    if hive.user_id != session['user_id']:
        abort(403)
    apiaries = Apiary.query.filter_by(user_id=session['user_id']).all()

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
    hive = db.session.get(Hive, id)
    if hive.user_id != session['user_id']:
        abort(403)
    db.session.delete(hive)  # Delete it from the session
    db.session.commit()  # Commit the changes to the database
    flash(f"Hive: {hive.name} deleted successfully!", "success")
    return redirect(url_for('hives'))  # Redirect back to the hives list

@app.route('/queens')
def queens():
    queens = Queen.query.filter_by(user_id=session['user_id']).all()
    return render_template('queens.html', queens=queens, active_page='queens')

@app.route('/add-queen', methods=['GET', 'POST'])
def add_queen():
    hives = [hive for hive in Hive.query.filter_by(user_id=session['user_id']).all() if not hive.queens]
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
        new_queen = Queen(name=name, breeder=breeder, birth_date=birth_date, hive_id=hive_id, user_id=session['user_id'])

        # Add to the database
        db.session.add(new_queen)
        db.session.commit()
        flash(f"Queen: {new_queen.name} added successfully!", "success")

        # Redirect to the hives list
        return redirect(url_for('queens'))

    
    return render_template('add_queen.html', hives=hives)

@app.route('/edit-queen/<int:id>', methods=['GET', 'POST'])
def edit_queen(id):
    queen = db.session.get(Queen, id)  # Fetch the Queen by ID
    if queen.user_id != session['user_id']:
        abort(403)

    # Find hives where no queen is currently assigned, include the current hive
    hives = Hive.query.filter_by(user_id=session['user_id']).filter(~Hive.queens.any()).all()
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
    queen = db.session.get(Queen, id)
    if queen.user_id != session['user_id']:
        abort(403)
    db.session.delete(queen)
    db.session.commit()  # Commit the changes to the database
    flash(f"Queen: {queen.name} deleted successfully!", "success")
    return redirect(url_for('queens'))  # Redirect back to the queens list

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password:
            flash('Password cannot be empty', 'danger')
            return redirect(url_for('change_password'))
        if not password_valid(new_password):
            flash('Password must be at least 8 characters long and include upper, lower and special characters.', 'danger')
            return redirect(url_for('change_password'))
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('change_password'))
        user.set_password(new_password)
        user.must_change_password = False
        db.session.commit()
        flash('Password updated successfully', 'success')
        return redirect(url_for('settings', open='security'))
    return render_template('change_password.html', active_page='settings')


@app.route('/setup-2fa', methods=['GET', 'POST'])
def setup_2fa():
    user = db.session.get(User, session['user_id'])
    if user.two_factor_secret:
        flash('Two-factor authentication is already enabled', 'info')
        return redirect(url_for('settings'))

    modal = request.args.get('modal')

    secret = session.get('tmp_2fa_secret')
    if not secret:
        secret = generate_totp_secret()
        session['tmp_2fa_secret'] = secret

    error = None
    if request.method == 'POST':
        token = request.form.get('token')
        if secret and verify_totp(secret, token):
            user.two_factor_secret = secret
            db.session.commit()
            session.pop('tmp_2fa_secret', None)
            flash('Two-factor authentication enabled', 'success')
            if modal:
                return jsonify(success=True)
            return redirect(url_for('settings'))
        error = 'Invalid authentication code'

    otpauth = f"otpauth://totp/Hiverr:{user.username}?secret={secret}&issuer=Hiverr"
    qr_data = None
    try:
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
        from qrcode.image.styles.colormasks import RadialGradiantColorMask

        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_Q,
            box_size=8,
            border=1,
        )
        qr.add_data(otpauth)
        qr.make(fit=True)
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=RadialGradiantColorMask(),
        )
        buf = BytesIO()
        img.save(buf, format="PNG")
        qr_data = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except ModuleNotFoundError:
        pass

    template = 'setup_2fa_inner.html' if modal else 'setup_2fa.html'
    return render_template(template, secret=secret, qr_data=qr_data, error=error)


@app.route('/disable-2fa', methods=['POST'])
def disable_2fa():
    user = db.session.get(User, session['user_id'])
    user.two_factor_secret = None
    db.session.commit()
    flash('Two-factor authentication disabled', 'success')
    return redirect(url_for('settings', open='security'))


@app.route('/toggle-registration', methods=['POST'])
def toggle_registration():
    user = db.session.get(User, session['user_id'])
    if user.role != 'admin':
        abort(403)
    enable = 'enable' in request.form
    cfg = db.session.get(Config, 'registration_enabled')
    if not cfg:
        cfg = Config(key='registration_enabled', value='0')
        db.session.add(cfg)
    cfg.value = '1' if enable else '0'
    db.session.commit()
    msg = 'User registration enabled' if enable else 'User registration disabled'
    if request.headers.get('Accept') == 'application/json':
        return jsonify(message=msg)
    flash(msg, 'success')
    return redirect(url_for('settings', open='security'))


@app.route('/create-user', methods=['POST'])
def create_user():
    admin = db.session.get(User, session['user_id'])
    if admin.role != 'admin':
        abort(403)
    full_name = request.form.get('full_name')
    email = request.form.get('email') or None
    username = request.form.get('username')
    password = request.form.get('password')
    force_change = request.form.get('force_change') == '1'
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('settings', open='users'))
    if not password_valid(password):
        flash('Password must be at least 8 characters long and include upper, lower and special characters.', 'danger')
        return redirect(url_for('settings', open='users'))
    new_user = User(username=username, full_name=full_name, email=email, must_change_password=force_change)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    flash('User created successfully', 'success')
    return redirect(url_for('settings', open='users'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user = db.session.get(User, session['user_id'])
    tz_list = sorted(available_timezones())
    if not user.timezone:
        tzinfo = datetime.now().astimezone().tzinfo
        user.timezone = getattr(tzinfo, 'key', tzinfo.tzname(None) or 'UTC')
        db.session.commit()
    if request.method == 'POST':
        section = request.form.get('section')
        if section == 'profile':
            user.full_name = request.form.get('full_name')
            user.username = request.form.get('username')
            email = request.form.get('email')
            user.email = email or None
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
                    filename = secure_filename(file.filename)
                    path = os.path.join('static', 'uploads', filename)
                    file.save(path)
                    user.profile_picture = path
        elif section == 'units':
            user.timezone = request.form.get('timezone')
            user.temperature_unit = request.form.get('temperature_unit')
            user.weight_unit = request.form.get('weight_unit')

        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings', open=section))

    return render_template('settings.html', user=user, timezones=tz_list, active_page='settings')

class Config(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200))


class Apiary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', backref='apiaries')

    hives = db.relationship('Hive', backref='apiary', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Apiary {self.name}>'

class Hive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    apiary_id = db.Column(db.Integer, db.ForeignKey('apiary.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', backref='hives')

    queens = db.relationship('Queen', backref='hive', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Hive {self.name}>'
    
class Queen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    breeder = db.Column(db.String(100))
    birth_date = db.Column(db.Date)
    hive_id = db.Column(db.Integer, db.ForeignKey('hive.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', backref='queens')

    def __repr__(self):
        return f'<Queen {self.name}>'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    role = db.Column(db.String(20), default='user')
    timezone = db.Column(db.String(50))
    temperature_unit = db.Column(db.String(10))
    weight_unit = db.Column(db.String(10))
    profile_picture = db.Column(db.String(200))
    two_factor_secret = db.Column(db.String(32))
    password_hash = db.Column(db.String(200), nullable=False)
    must_change_password = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@app.context_processor
def inject_sidebar_apiaries():
    if 'user_id' in session:
        apiaries = Apiary.query.filter_by(user_id=session['user_id']).all()
    else:
        apiaries = []
    return {'sidebar_apiaries': apiaries}


@app.context_processor
def inject_current_user():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        return {'current_user': user}
    return {}


@app.context_processor
def inject_registration_flag():
    return {'registration_enabled': registration_enabled()}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=80)
