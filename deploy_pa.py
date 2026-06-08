import os

BASE = '/home/NLCFMAIN/Feedback-Form'

files = {}

files['app.py'] = r"""from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import pandas as pd
import io
import os
import logging

PHT = timezone(timedelta(hours=8))

def to_pht(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(PHT)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'feedback-secret-key-change-in-production')

if not app.debug:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
else:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

basedir = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get('DATABASE_URL')

if database_url and ('postgres' in database_url or 'supabase' in database_url):
    if 'sslmode' not in database_url:
        database_url += '?sslmode=require'
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10, 'max_overflow': 20, 'pool_recycle': 60, 'pool_pre_ping': True, 'pool_use_lifo': True
    }
else:
    database_url = f'sqlite:///{os.path.join(basedir, "instance", "feedback.db")}'
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

db = SQLAlchemy(app)

if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False}, 'pool_pre_ping': True
    }

login_manager = LoginManager(app)
login_manager.login_view = 'nlcf_login'
login_manager.login_message_category = 'info'


@app.template_filter('pht')
def pht_format(dt, fmt='%b %d, %Y %I:%M %p'):
    if dt is None:
        return ''
    return to_pht(dt).strftime(fmt)


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=True)
    church_location = db.Column(db.String(200), nullable=True)
    age_group = db.Column(db.String(50), nullable=True)
    first_time_attending = db.Column(db.String(10), nullable=True)
    participant_category = db.Column(db.String(50), nullable=True)
    rating_registration = db.Column(db.String(20), nullable=True)
    rating_venue = db.Column(db.String(20), nullable=True)
    rating_program_flow = db.Column(db.String(20), nullable=True)
    rating_av = db.Column(db.String(20), nullable=True)
    rating_worship = db.Column(db.String(20), nullable=True)
    rating_speakers = db.Column(db.String(20), nullable=True)
    rating_fellowship = db.Column(db.String(20), nullable=True)
    rating_food = db.Column(db.String(20), nullable=True)
    rating_organization = db.Column(db.String(20), nullable=True)
    rating_overall = db.Column(db.String(20), nullable=True)
    most_impactful_part = db.Column(db.String(100), nullable=True)
    most_impactful_other = db.Column(db.String(200), nullable=True)
    enjoyed_most = db.Column(db.Text, nullable=True)
    areas_for_improvement = db.Column(db.Text, nullable=True)
    announcements_clarity = db.Column(db.String(50), nullable=True)
    faith_strengthened = db.Column(db.String(50), nullable=True)
    spiritual_lesson = db.Column(db.Text, nullable=True)
    connected_to_nlcf = db.Column(db.String(20), nullable=True)
    attend_future = db.Column(db.String(20), nullable=True)
    future_topics = db.Column(db.Text, nullable=True)
    testimony = db.Column(db.Text, nullable=True)
    final_comments = db.Column(db.Text, nullable=True)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


@app.route('/')
def index():
    return render_template('index.html')


REQUIRED_FIELDS = [
    'age_group', 'first_time_attending',
    'participant_category',
    'rating_registration', 'rating_venue', 'rating_program_flow', 'rating_av',
    'rating_worship', 'rating_speakers', 'rating_fellowship', 'rating_food',
    'rating_organization', 'rating_overall',
    'most_impactful_part', 'announcements_clarity',
    'faith_strengthened', 'connected_to_nlcf', 'attend_future'
]

REQUIRED_LABELS = {
    'age_group': 'Age Group',
    'first_time_attending': 'First time attending?',
    'participant_category': 'Participant Category',
    'rating_registration': 'Rating: Registration',
    'rating_venue': 'Rating: Venue & Facilities',
    'rating_program_flow': 'Rating: Program Flow',
    'rating_av': 'Rating: Audio & Visual',
    'rating_worship': 'Rating: Praise & Worship',
    'rating_speakers': 'Rating: Messages/Speakers',
    'rating_fellowship': 'Rating: Fellowship',
    'rating_food': 'Rating: Food & Refreshments',
    'rating_organization': 'Rating: Organization',
    'rating_overall': 'Rating: Overall Experience',
    'most_impactful_part': 'Most impactful part',
    'announcements_clarity': 'Announcements clarity',
    'faith_strengthened': 'Faith strengthened',
    'connected_to_nlcf': 'Connected to NLCF',
    'attend_future': 'Attend future events'
}


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        data = request.form

        missing = [REQUIRED_LABELS[f] for f in REQUIRED_FIELDS if not data.get(f, '').strip()]
        if missing:
            flash(f'Please fill in all required fields: {", ".join(missing)}.', 'danger')
            return render_template('feedback.html', data=data)

        feedback_entry = Feedback(
            name=data.get('name', '').strip(),
            church_location=data.get('church_location', '').strip(),
            age_group=data.get('age_group', ''),
            first_time_attending=data.get('first_time_attending', ''),
            participant_category=data.get('participant_category', ''),
            rating_registration=data.get('rating_registration', ''),
            rating_venue=data.get('rating_venue', ''),
            rating_program_flow=data.get('rating_program_flow', ''),
            rating_av=data.get('rating_av', ''),
            rating_worship=data.get('rating_worship', ''),
            rating_speakers=data.get('rating_speakers', ''),
            rating_fellowship=data.get('rating_fellowship', ''),
            rating_food=data.get('rating_food', ''),
            rating_organization=data.get('rating_organization', ''),
            rating_overall=data.get('rating_overall', ''),
            most_impactful_part=data.get('most_impactful_part', ''),
            most_impactful_other=data.get('most_impactful_other', '').strip(),
            enjoyed_most=data.get('enjoyed_most', '').strip(),
            areas_for_improvement=data.get('areas_for_improvement', '').strip(),
            announcements_clarity=data.get('announcements_clarity', ''),
            faith_strengthened=data.get('faith_strengthened', ''),
            spiritual_lesson=data.get('spiritual_lesson', '').strip(),
            connected_to_nlcf=data.get('connected_to_nlcf', ''),
            attend_future=data.get('attend_future', ''),
            future_topics=data.get('future_topics', '').strip(),
            testimony=data.get('testimony', '').strip(),
            final_comments=data.get('final_comments', '').strip()
        )
        try:
            db.session.add(feedback_entry)
            db.session.commit()
            flash('Thank you for your valuable feedback! Your responses have been recorded.', 'success')
            return render_template('feedback_thankyou.html')
        except Exception as e:
            db.session.rollback()
            logging.error(f'Feedback submission error: {str(e)}')
            flash('An error occurred while submitting your feedback. Please try again.', 'danger')
            return render_template('feedback.html', data=data)
    return render_template('feedback.html', data={})


@app.route('/login', methods=['GET', 'POST'])
def nlcf_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def nlcf_logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/nlcfadmin.SystemAdmin')
@login_required
def admin():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    feedbacks = Feedback.query
    search = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if search:
        feedbacks = feedbacks.filter(
            (Feedback.name.contains(search)) |
            (Feedback.church_location.contains(search)) |
            (Feedback.enjoyed_most.contains(search)) |
            (Feedback.final_comments.contains(search))
        )

    if date_from:
        feedbacks = feedbacks.filter(Feedback.submission_date >= datetime.strptime(date_from, '%Y-%m-%d'))

    if date_to:
        feedbacks = feedbacks.filter(Feedback.submission_date <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))

    feedbacks = feedbacks.order_by(Feedback.submission_date.desc())
    pagination = feedbacks.paginate(page=page, per_page=per_page, error_out=False)
    feedbacks = pagination.items

    total = Feedback.query.count()

    rating_fields = ['rating_registration', 'rating_venue', 'rating_program_flow', 'rating_av',
                     'rating_worship', 'rating_speakers', 'rating_fellowship', 'rating_food',
                     'rating_organization', 'rating_overall']
    rating_labels = ['Registration', 'Venue & Facilities', 'Program Flow', 'Audio & Visual',
                     'Praise & Worship', 'Messages/Speakers', 'Fellowship', 'Food & Refreshments',
                     'Organization', 'Overall']

    rating_data = []
    for field, label in zip(rating_fields, rating_labels):
        rows = db.session.query(
            getattr(Feedback, field).label('rating'),
            db.func.count(Feedback.id)
        ).filter(
            getattr(Feedback, field) != ''
        ).group_by(getattr(Feedback, field)).all()

        dist = {'Excellent': 0, 'Good': 0, 'Fair': 0, 'Poor': 0}
        for rating, count in rows:
            if rating in dist:
                dist[rating] = count
        rating_data.append({'label': label, 'field': field, 'dist': dist})

    age_distribution = db.session.query(
        Feedback.age_group, db.func.count(Feedback.id)
    ).filter(Feedback.age_group != '').group_by(Feedback.age_group).all()
    age_dist = dict(age_distribution)

    first_time_count = Feedback.query.filter_by(first_time_attending='Yes').count()

    return render_template('admin.html',
                           feedbacks=feedbacks,
                           total=total,
                           rating_data=rating_data,
                           age_dist=age_dist,
                           total_feedback=total,
                           first_time_count=first_time_count,
                           search=search,
                           date_from=date_from,
                           date_to=date_to,
                           pagination=pagination)


@app.route('/nlcfadmin.SystemAdmin/feedback/<int:id>')
@login_required
def get_feedback(id):
    fb = db.session.get(Feedback, id)
    if not fb:
        return jsonify({'error': 'Not found'}), 404
    rating_fields = [
        ('Registration', fb.rating_registration),
        ('Venue & Facilities', fb.rating_venue),
        ('Program Flow', fb.rating_program_flow),
        ('Audio & Visual', fb.rating_av),
        ('Praise & Worship', fb.rating_worship),
        ('Messages/Speakers', fb.rating_speakers),
        ('Fellowship', fb.rating_fellowship),
        ('Food & Refreshments', fb.rating_food),
        ('Organization', fb.rating_organization),
        ('Overall', fb.rating_overall),
    ]
    ratings = {label: val for label, val in rating_fields if val}
    return jsonify({
        'id': fb.id, 'name': fb.name, 'church_location': fb.church_location,
        'age_group': fb.age_group, 'first_time_attending': fb.first_time_attending,
        'participant_category': fb.participant_category,
        'ratings': ratings,
        'most_impactful_part': fb.most_impactful_part,
        'most_impactful_other': fb.most_impactful_other,
        'enjoyed_most': fb.enjoyed_most, 'areas_for_improvement': fb.areas_for_improvement,
        'announcements_clarity': fb.announcements_clarity,
        'faith_strengthened': fb.faith_strengthened, 'spiritual_lesson': fb.spiritual_lesson,
        'connected_to_nlcf': fb.connected_to_nlcf, 'attend_future': fb.attend_future,
        'future_topics': fb.future_topics, 'testimony': fb.testimony,
        'final_comments': fb.final_comments,
        'submission_date': to_pht(fb.submission_date).strftime('%b %d, %Y %I:%M %p') if fb.submission_date else ''
    })


@app.route('/nlcfadmin.SystemAdmin/feedback/<int:id>/delete', methods=['POST'])
@login_required
def delete_feedback(id):
    try:
        fb = db.session.get(Feedback, id)
        if fb:
            db.session.delete(fb)
            db.session.commit()
            flash('Feedback deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f'Delete feedback error: {str(e)}')
        flash('An error occurred. Please try again.', 'danger')
    return redirect(url_for('admin'))


@app.route('/export')
@login_required
def export():
    try:
        feedbacks = Feedback.query.all()
        data = []
        for fb in feedbacks:
            data.append({
                'ID': fb.id, 'Name': fb.name or '', 'Church/Location': fb.church_location or '',
                'Age Group': fb.age_group or '', 'First Time Attending': fb.first_time_attending or '',
                'Participant Category': fb.participant_category or '',
                'Rating - Registration': fb.rating_registration or '',
                'Rating - Venue': fb.rating_venue or '', 'Rating - Program Flow': fb.rating_program_flow or '',
                'Rating - AV': fb.rating_av or '', 'Rating - Worship': fb.rating_worship or '',
                'Rating - Speakers': fb.rating_speakers or '',
                'Rating - Fellowship': fb.rating_fellowship or '',
                'Rating - Food': fb.rating_food or '',
                'Rating - Organization': fb.rating_organization or '',
                'Rating - Overall': fb.rating_overall or '',
                'Most Impactful Part': fb.most_impactful_part or '',
                'Most Impactful Other': fb.most_impactful_other or '',
                'Enjoyed Most': fb.enjoyed_most or '',
                'Areas for Improvement': fb.areas_for_improvement or '',
                'Announcements Clarity': fb.announcements_clarity or '',
                'Faith Strengthened': fb.faith_strengthened or '',
                'Spiritual Lesson': fb.spiritual_lesson or '',
                'Connected to NLCF': fb.connected_to_nlcf or '',
                'Attend Future': fb.attend_future or '',
                'Future Topics': fb.future_topics or '',
                'Testimony': fb.testimony or '',
                'Final Comments': fb.final_comments or '',
                'Submission Date': to_pht(fb.submission_date).strftime('%Y-%m-%d %H:%M:%S') if fb.submission_date else ''
            })
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Feedback', index=False)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'feedback_{datetime.now(PHT).strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'Export error: {str(e)}')
        flash('An error occurred during export.', 'danger')
        return redirect(url_for('admin'))


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now(PHT).isoformat(), 'version': 1})


@app.after_request
def add_security_headers(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 3600
        response.cache_control.public = True
    return response


@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', title='404 - Page Not Found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('base.html', title='500 - Server Error'), 500


def migrate_database():
    try:
        from sqlalchemy import inspect as _inspect
        inspector = _inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('feedback')]
        if 'participant_category' not in columns:
            db.session.execute(db.text("ALTER TABLE feedback ADD COLUMN participant_category VARCHAR(50)"))
            db.session.commit()
            logging.info("Migration: added participant_category column")
    except Exception as e:
        db.session.rollback()
        logging.warning(f"Migration skipped or failed: {e}")


def init_database():
    with app.app_context():
        from sqlalchemy import event as _event

        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            @_event.listens_for(db.engine, 'connect')
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-64000")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        db.create_all()
        migrate_database()

        old = Admin.query.filter_by(username='admin').first()
        if old:
            db.session.delete(old)

        if not Admin.query.filter_by(username='SystemAdmin').first():
            default_password = os.environ.get('ADMIN_PASSWORD', 'nlcfadmin2026')
            admin = Admin(username='SystemAdmin')
            admin.set_password(default_password)
            db.session.add(admin)

        db.session.commit()


_db_init_done = False


@app.before_request
def ensure_db_init():
    global _db_init_done
    if not request.endpoint or request.endpoint == 'health' or request.path.startswith('/static/'):
        return
    if not _db_init_done:
        try:
            init_database()
            _db_init_done = True
        except Exception as e:
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'not set') or 'not set'
            masked = db_uri[:30] + '...'
            logging.error(f"DB init failed. URI: {masked}. Error: {e}")
            return f"Database error. Check that DATABASE_URL is set correctly. URI: {masked}<br>Details: {e}", 503


try:
    init_database()
    _db_init_done = True
except Exception as e:
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'not set') or 'not set'
    logging.warning(f"DB init on startup failed (will retry on first request): {e}. URI: {db_uri[:30]}...")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    logging.info(f'Starting Feedback Form server on port {port}')
    app.run(host='0.0.0.0', port=port, threaded=True)
"""

files['requirements.txt'] = """Flask>=3.0
Flask-SQLAlchemy>=3.1
Flask-Login>=0.6
Flask-WTF>=1.2
Werkzeug>=3.0
pandas>=2.0
openpyxl>=3.1
"""

files['templates/base.html'] = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{% block title %}NLCF Feedback Form{% endblock %}</title>
    <link rel="icon" href="{{ url_for('static', filename='img/Logo.jpg') }}" type="image/jpeg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    {% block extra_head %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg sticky-top">
        <div class="container">
            <a class="navbar-brand animate-up" href="{{ url_for('index') }}">
                <img src="{{ url_for('static', filename='img/Logo.jpg') }}" alt="Logo">
                <span class="d-none d-sm-inline">NLCF Feedback Form</span>
                <span class="d-inline d-sm-none">NLCF</span>
            </a>
            <button class="navbar-toggler border-0 shadow-none" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <div class="navbar-nav ms-auto gap-2">
                    <a class="nav-link {% if request.endpoint == 'index' %}active{% endif %}" href="{{ url_for('index') }}">Home</a>
                    {% if current_user.is_authenticated %}
                    <a class="nav-link {% if request.endpoint == 'admin' %}active{% endif %}" href="{{ url_for('admin') }}">Dashboard</a>
                    <a class="nav-link text-danger" href="{{ url_for('nlcf_logout') }}"><i class="bi bi-box-arrow-right me-1"></i>Logout</a>
                    {% else %}
                    <a class="nav-link {% if request.endpoint == 'feedback' %}active{% endif %}" href="{{ url_for('feedback') }}">Give Feedback</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    <main class="flex-grow-1 py-4 py-md-5">
        <div class="container">
            {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
            {% for category, message in messages %}
            {% set alert_class = category if category in ['danger', 'success', 'warning', 'info'] else 'info' %}
            {% set icon_map = {'danger': 'exclamation-circle', 'success': 'check-circle', 'warning': 'exclamation-triangle', 'info': 'info-circle'} %}
            <div class="alert alert-{{ alert_class }} glass-card border-0 animate-up mb-4" role="alert">
                <div class="d-flex align-items-center gap-2">
                    <i class="bi bi-{{ icon_map.get(category, 'info-circle') }}"></i>
                    <div>{{ message }}</div>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
            {% endfor %}
            {% endif %}
            {% endwith %}
            {% block content %}{% endblock %}
        </div>
    </main>
    <footer class="footer">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-md-6 text-center text-md-start">
                    <p class="footer-text mb-0">&copy; 2026 New Life In Christ Fellowship. All rights reserved.</p>
                </div>
                <div class="col-md-6 text-center text-md-end mt-3 mt-md-0">
                    <p class="footer-text mb-0">
                        <span class="badge bg-light text-dark border fw-normal py-2 px-3">Feedback System v1.0</span>
                    </p>
                </div>
            </div>
        </div>
    </footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
"""

files['templates/index.html'] = """{% extends "base.html" %}

{% block title %}NLCF 45th Annual Reunion - Feedback Form{% endblock %}

{% block content %}
<div class="row justify-content-center animate-up">
    <div class="col-lg-8 text-center" style="padding: 80px 0;">
        <div class="mb-4">
            <img src="{{ url_for('static', filename='img/Logo.jpg') }}" alt="NLCF Logo" style="width: 120px; height: 120px; border-radius: 20px; box-shadow: var(--shadow-lg);">
        </div>
        <h1 class="display-4 fw-bold mb-3">NLCF 45th Annual Reunion</h1>
        <p class="text-gradient display-6 fw-bold mb-3">&amp; Church Anniversary</p>
        <p class="lead text-muted mb-4" style="font-size: 1.2rem;">Honoring our Past, Celebrating our Present, Inspiring our Future</p>
        <p class="text-muted mb-5" style="max-width: 600px; margin: 0 auto;">Your feedback helps us improve future church events and better serve our church family.</p>
            <div class="d-flex gap-3 justify-content-center">
                <a href="{{ url_for('feedback') }}" class="btn btn-primary btn-lg px-5 py-3">
                    <i class="bi bi-pencil-square me-2"></i>Give Feedback
                </a>
            </div>
    </div>
</div>
{% endblock %}
"""

files['templates/feedback.html'] = """{% extends "base.html" %}

{% block title %}Feedback Form - NLCF 45th Annual Reunion{% endblock %}

{% block extra_head %}
<style>
    :root {
        --radio-size: 20px;
        --radio-border: #cbd5e1;
        --radio-checked: var(--accent);
    }
    .feedback-header {
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        border-radius: var(--radius-lg);
        padding: 32px 24px;
        color: white;
        margin-bottom: 40px;
        box-shadow: var(--shadow-xl);
        text-align: center;
    }
    .feedback-header h1 { color: white; margin-bottom: 8px; font-size: clamp(1.3rem, 5vw, 2.5rem); }
    .feedback-header .subtitle { opacity: 1; color: white; font-size: clamp(0.85rem, 2.5vw, 1rem); font-weight: 400; }
    .feedback-header p { opacity: 1; color: white; font-weight: 600; margin-bottom: 0; font-size: clamp(0.9rem, 2.5vw, 1.05rem); }
    .form-section {
        background: white;
        border-radius: var(--radius-lg);
        padding: clamp(20px, 4vw, 32px);
        margin-bottom: 20px;
        box-shadow: var(--shadow-md);
        border: 1px solid rgba(0,0,0,0.04);
        position: relative;
    }
    .form-section::before {
        content: '';
        position: absolute;
        top: 0; left: 24px; right: 24px;
        height: 3px;
        background: linear-gradient(90deg, var(--accent), var(--secondary), var(--accent));
        border-radius: 0 0 3px 3px;
        opacity: 0.5;
    }
    .form-section h4 {
        color: var(--accent);
        font-weight: 700;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 2px solid #f1f5f9;
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: clamp(1rem, 4vw, 1.3rem);
    }

    /* ---- Rating Rows (mobile-first) ---- */
    .rating-row {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 14px 16px;
        border-bottom: 1px solid #f1f5f9;
        background: white;
    }
    .rating-row:last-child { border-bottom: none; }
    .rating-row .rating-label {
        font-weight: 600;
        font-size: 0.9rem;
        color: var(--text-main);
    }
    .rating-row .rating-options {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }
    .rating-row .rating-option {
        flex: 1 0 auto;
        min-width: 0;
    }
    .rating-row .rating-option input[type="radio"] {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
        pointer-events: none;
    }
    .rating-row .rating-option label {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 10px 12px;
        border: 2px solid #e2e8f0;
        border-radius: 100px;
        cursor: pointer;
        transition: all 0.2s ease;
        font-weight: 500;
        font-size: 0.82rem;
        color: var(--text-main);
        background: white;
        user-select: none;
        text-align: center;
    }
    .rating-row .rating-option label::before {
        content: '';
        width: 16px;
        height: 16px;
        border: 2px solid var(--radio-border);
        border-radius: 50%;
        flex-shrink: 0;
        transition: all 0.2s ease;
        display: inline-block;
    }
    .rating-row .rating-option label:hover {
        border-color: var(--accent);
        background: rgba(85, 107, 47, 0.04);
    }
    .rating-row .rating-option label:hover::before { border-color: var(--accent); }
    .rating-row .rating-option input[type="radio"]:checked + label {
        border-color: var(--accent);
        background: rgba(85, 107, 47, 0.07);
        color: var(--accent);
        font-weight: 600;
    }
    .rating-row .rating-option input[type="radio"]:checked + label::before {
        border-color: var(--accent);
        border-width: 6px;
    }
    @media (min-width: 768px) {
        .rating-row {
            flex-direction: row;
            align-items: center;
            gap: 16px;
        }
        .rating-row .rating-label {
            width: 200px;
            flex-shrink: 0;
        }
        .rating-row .rating-options {
            flex: 1;
            display: flex;
            gap: 8px;
        }
        .rating-row .rating-option {
            flex: 1;
        }
        .rating-row .rating-option label {
            font-size: 0.85rem;
            padding: 10px 16px;
        }
    }

    /* ---- Radio Group (pill buttons) ---- */
    .radio-group {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
    }
    .radio-group .form-check {
        padding: 0;
        margin: 0;
        min-width: 80px;
    }
    .radio-group .form-check input[type="radio"] {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
        pointer-events: none;
    }
    .radio-group .form-check label {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 10px 20px;
        border: 2px solid #e2e8f0;
        border-radius: 100px;
        cursor: pointer;
        transition: all 0.2s ease;
        font-weight: 500;
        font-size: 0.9rem;
        color: var(--text-main);
        background: white;
        user-select: none;
        white-space: nowrap;
    }
    .radio-group .form-check label::before {
        content: '';
        width: 18px;
        height: 18px;
        border: 2px solid var(--radio-border);
        border-radius: 50%;
        flex-shrink: 0;
        transition: all 0.2s ease;
        display: inline-block;
    }
    .radio-group .form-check label:hover {
        border-color: var(--accent);
        background: rgba(85, 107, 47, 0.04);
    }
    .radio-group .form-check label:hover::before {
        border-color: var(--accent);
    }
    .radio-group .form-check input[type="radio"]:checked + label {
        border-color: var(--accent);
        background: rgba(85, 107, 47, 0.07);
        color: var(--accent);
        font-weight: 600;
    }
    .radio-group .form-check input[type="radio"]:checked + label::before {
        border-color: var(--accent);
        border-width: 6px;
    }

    .other-input { margin-top: 10px; padding-left: 12px; }
    .text-danger { color: var(--danger) !important; font-weight: 700; }

    /* ---- Responsive tweaks ---- */
    @media (max-width: 576px) {
        .feedback-header { padding: 24px 16px; border-radius: var(--radius-md); }
        .form-section { border-radius: var(--radius-md); padding: 18px; }
        .radio-group { gap: 8px; }
        .radio-group .form-check { min-width: 0; flex: 1 1 auto; }
        .radio-group .form-check label {
            padding: 8px 12px;
            font-size: 0.78rem;
            gap: 4px;
        }
        .radio-group .form-check label::before {
            width: 14px; height: 14px;
        }
        .rating-row { padding: 12px 14px; gap: 6px; }
        .rating-row .rating-label { font-size: 0.82rem; }
        .rating-row .rating-option label {
            padding: 8px 10px;
            font-size: 0.72rem;
            gap: 4px;
        }
        .rating-row .rating-option label::before {
            width: 14px; height: 14px;
        }
    }
</style>
{% endblock %}

{% block content %}
<div class="feedback-header animate-up">
    <h1 class="fw-bold">NLCF 45th Annual Reunion<br class="d-sm-none"> &amp; Church Anniversary</h1>
    <p class="mb-0">Participant Feedback Form</p>
    <p class="mt-2 mb-0 subtitle">Thank you for attending our celebration! Your feedback will help us improve future church events and better serve our church family.</p>
</div>

<form method="POST" action="{{ url_for('feedback') }}" class="animate-up" style="animation-delay: 0.1s">
    <div class="text-end mb-3 small text-muted"><span class="text-danger">*</span> Required fields</div>
    <div class="form-section">
        <h4><i class="bi bi-person me-2"></i>Basic Information</h4>
        <div class="row g-4">
            <div class="col-md-6">
                <label class="form-label">Name <span class="text-muted fw-normal">(Optional)</span></label>
                <input type="text" class="form-control" name="name" placeholder="Your name" value="{{ data.get('name', '') }}">
            </div>
            <div class="col-md-6">
                <label class="form-label">Church / Location</label>
                <input type="text" class="form-control" name="church_location" placeholder="Your church or location" value="{{ data.get('church_location', '') }}">
            </div>
            <div class="col-md-6">
                <label class="form-label">Age Group <span class="text-danger">*</span></label>
                <div class="radio-group">
                    {% for option in ['Below 18', '18-30', '31-45', '46-60', '61 and above'] %}
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="age_group" value="{{ option }}" id="age_{{ loop.index }}" {% if data.get('age_group') == option %}checked{% endif %} required>
                        <label class="form-check-label" for="age_{{ loop.index }}">{{ option }}</label>
                    </div>
                    {% endfor %}
                </div>
            </div>
            <div class="col-md-6">
                <label class="form-label">Is this your first time attending an NLCF Anniversary/Reunion? <span class="text-danger">*</span></label>
                <div class="radio-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="first_time_attending" value="Yes" id="first_yes" {% if data.get('first_time_attending') == 'Yes' %}checked{% endif %} required>
                        <label class="form-check-label" for="first_yes">Yes</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="first_time_attending" value="No" id="first_no" {% if data.get('first_time_attending') == 'No' %}checked{% endif %} required>
                        <label class="form-check-label" for="first_no">No</label>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="form-section">
        <h4><i class="bi bi-star me-2"></i>Event Evaluation</h4>
        <p class="text-muted mb-4">Please rate the following: <span class="text-danger">*</span></p>
        <div class="border rounded-3 overflow-hidden">
            {% set ratings = [
                ('rating_registration', 'Registration Process'),
                ('rating_venue', 'Venue & Facilities'),
                ('rating_program_flow', 'Program Flow'),
                ('rating_av', 'Audio & Visual Presentation'),
                ('rating_worship', 'Praise & Worship'),
                ('rating_speakers', 'Messages/Speakers'),
                ('rating_fellowship', 'Fellowship Experience'),
                ('rating_food', 'Food & Refreshments'),
                ('rating_organization', 'Event Organization'),
                ('rating_overall', 'Overall Experience')
            ] %}
            {% for field, label in ratings %}
            <div class="rating-row">
                <div class="rating-label">{{ label }}</div>
                <div class="rating-options">
                    {% for val in ['Excellent', 'Good', 'Fair', 'Poor'] %}
                    <div class="rating-option">
                        <input type="radio" name="{{ field }}" value="{{ val }}" id="{{ field }}_{{ loop.index }}" {% if data.get(field) == val %}checked{% endif %} required>
                        <label for="{{ field }}_{{ loop.index }}">{{ val }}</label>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="form-section">
        <h4><i class="bi bi-chat-quote me-2"></i>Program Feedback</h4>
        <div class="mb-4">
            <label class="form-label">1. Which part of the program impacted you the most? <span class="text-danger">*</span></label>
            <div class="radio-group">
                {% for option in ['Praise & Worship', 'Testimonies', 'Anniversary Celebration', 'Reunion Fellowship', 'Graduation Ceremony', 'Main Message', 'Special Presentations'] %}
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="most_impactful_part" value="{{ option }}" id="impact_{{ loop.index }}" {% if data.get('most_impactful_part') == option %}checked{% endif %} required>
                    <label class="form-check-label" for="impact_{{ loop.index }}">{{ option }}</label>
                </div>
                {% endfor %}
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="most_impactful_part" value="Other" id="impact_other" {% if data.get('most_impactful_part') == 'Other' %}checked{% endif %} required>
                    <label class="form-check-label" for="impact_other">Other</label>
                </div>
            </div>
            <div class="other-input" id="impact_other_div" {% if data.get('most_impactful_part') != 'Other' %}style="display:none"{% endif %}>
                <input type="text" class="form-control" name="most_impactful_other" placeholder="Please specify..." value="{{ data.get('most_impactful_other', '') }}">
            </div>
        </div>
        <div class="mb-4">
            <label class="form-label">2. What did you enjoy most about the event?</label>
            <textarea class="form-control" name="enjoyed_most" rows="3" placeholder="Share your thoughts...">{{ data.get('enjoyed_most', '') }}</textarea>
        </div>
        <div class="mb-4">
            <label class="form-label">3. What areas can we improve for future events?</label>
            <textarea class="form-control" name="areas_for_improvement" rows="3" placeholder="Your suggestions...">{{ data.get('areas_for_improvement', '') }}</textarea>
        </div>
        <div>
            <label class="form-label">4. Were the event announcements and instructions clear? <span class="text-danger">*</span></label>
            <div class="radio-group">
                {% for option in ['Very Clear', 'Clear', 'Somewhat Clear', 'Not Clear'] %}
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="announcements_clarity" value="{{ option }}" id="clarity_{{ loop.index }}" {% if data.get('announcements_clarity') == option %}checked{% endif %} required>
                    <label class="form-check-label" for="clarity_{{ loop.index }}">{{ option }}</label>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <div class="form-section">
        <h4><i class="bi bi-heart me-2"></i>Spiritual Impact</h4>
        <div class="mb-4">
            <label class="form-label">1. Did this event strengthen your faith and relationship with God? <span class="text-danger">*</span></label>
            <div class="radio-group">
                {% for option in ['Strongly Agree', 'Agree', 'Neutral', 'Disagree'] %}
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="faith_strengthened" value="{{ option }}" id="faith_{{ loop.index }}" {% if data.get('faith_strengthened') == option %}checked{% endif %} required>
                    <label class="form-check-label" for="faith_{{ loop.index }}">{{ option }}</label>
                </div>
                {% endfor %}
            </div>
        </div>
        <div class="mb-4">
            <label class="form-label">2. What spiritual lesson or message did you take home from this event?</label>
            <textarea class="form-control" name="spiritual_lesson" rows="3" placeholder="Share what God spoke to your heart...">{{ data.get('spiritual_lesson', '') }}</textarea>
        </div>
        <div>
            <label class="form-label">3. Do you feel more connected to the NLCF family after attending? <span class="text-danger">*</span></label>
            <div class="radio-group">
                {% for option in ['Yes', 'Somewhat', 'No'] %}
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="connected_to_nlcf" value="{{ option }}" id="connect_{{ loop.index }}" {% if data.get('connected_to_nlcf') == option %}checked{% endif %} required>
                    <label class="form-check-label" for="connect_{{ loop.index }}">{{ option }}</label>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <div class="form-section">
        <h4><i class="bi bi-calendar-event me-2"></i>Future Events</h4>
        <div class="mb-4">
            <label class="form-label">1. Would you attend future NLCF Anniversary/Reunion events? <span class="text-danger">*</span></label>
            <div class="radio-group">
                {% for option in ['Definitely', 'Probably', 'Not Sure', 'No'] %}
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="attend_future" value="{{ option }}" id="future_{{ loop.index }}" {% if data.get('attend_future') == option %}checked{% endif %} required>
                    <label class="form-check-label" for="future_{{ loop.index }}">{{ option }}</label>
                </div>
                {% endfor %}
            </div>
        </div>
        <div>
            <label class="form-label">2. What activities or topics would you like to see in future events?</label>
            <textarea class="form-control" name="future_topics" rows="3" placeholder="Your ideas...">{{ data.get('future_topics', '') }}</textarea>
        </div>
    </div>

    <div class="form-section">
        <h4><i class="bi bi-megaphone me-2"></i>Testimony <span class="text-muted fw-normal">(Optional)</span></h4>
        <p class="text-muted mb-3">If God moved in your life through this event, we would love to hear your testimony:</p>
        <textarea class="form-control" name="testimony" rows="4" placeholder="Share your testimony...">{{ data.get('testimony', '') }}</textarea>
    </div>

    <div class="form-section">
        <h4><i class="bi bi-pencil me-2"></i>Final Comments or Suggestions</h4>
        <textarea class="form-control" name="final_comments" rows="3" placeholder="Any final thoughts?">{{ data.get('final_comments', '') }}</textarea>
    </div>

    <div class="text-center mb-5 animate-up" style="animation-delay: 0.3s">
        <div class="card border-0 shadow-lg p-4 p-md-5 mb-4" style="background: linear-gradient(135deg, #fafbfc 0%, white 100%);">
            <p class="text-muted mb-4" style="max-width: 500px; margin: 0 auto;">Before you submit, please review your responses. Every feedback helps us create better experiences for our church family.</p>
            <button type="submit" class="btn btn-primary btn-lg px-5 py-3 rounded-pill shadow-lg" style="font-size: 1.05rem;">
                <i class="bi bi-send me-2"></i>Submit Feedback
            </button>
        </div>
        <p class="text-muted fst-italic" style="font-size: 0.95rem;">&ldquo;To God be all the glory!&rdquo;</p>
    </div>
</form>
{% endblock %}

{% block scripts %}
<script>
function toggleImpactOther() {
    const otherRadio = document.getElementById('impact_other');
    const otherDiv = document.getElementById('impact_other_div');
    if (otherRadio) {
        otherDiv.style.display = otherRadio.checked ? 'block' : 'none';
    }
}
document.querySelectorAll('input[name="most_impactful_part"]').forEach(function(r) {
    r.addEventListener('change', toggleImpactOther);
});
</script>
{% endblock %}
"""

files['templates/login.html'] = """{% extends "base.html" %}

{% block title %}Admin Login - NLCF Feedback{% endblock %}

{% block extra_head %}
<style>
    .login-wrapper {
        min-height: calc(100vh - var(--nav-height) - 200px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px 0;
    }
    .login-card {
        width: 100%;
        max-width: 420px;
    }
    .login-card .card {
        border-radius: var(--radius-lg);
        overflow: hidden;
    }
    .login-accent {
        height: 4px;
        background: linear-gradient(90deg, var(--accent), var(--secondary));
    }
    .login-icon {
        width: 56px; height: 56px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--accent), var(--secondary));
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        margin: 0 auto 16px;
        box-shadow: 0 4px 15px rgba(85,107,47,0.25);
    }
</style>
{% endblock %}

{% block content %}
<div class="login-wrapper animate-up">
    <div class="login-card">
        <div class="card border-0 shadow-lg">
            <div class="login-accent"></div>
            <div class="card-body p-5">
                <div class="text-center mb-4">
                    <div class="login-icon">
                        <i class="bi bi-shield-lock"></i>
                    </div>
                    <h4 class="fw-bold mb-1">Admin Portal</h4>
                    <p class="text-muted small">Sign in to manage feedback</p>
                </div>
                <form method="POST" action="{{ url_for('nlcf_login') }}">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <div class="input-group">
                            <span class="input-group-text bg-light border-end-0"><i class="bi bi-person"></i></span>
                            <input type="text" class="form-control border-start-0" name="username" placeholder="Enter username" required autofocus>
                        </div>
                    </div>
                    <div class="mb-4">
                        <label class="form-label">Password</label>
                        <div class="input-group">
                            <span class="input-group-text bg-light border-end-0"><i class="bi bi-lock"></i></span>
                            <input type="password" class="form-control border-start-0" name="password" placeholder="Enter password" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 py-2 rounded-pill">
                        <i class="bi bi-box-arrow-in-right me-2"></i>Sign In
                    </button>
                </form>
            </div>
            <div class="card-footer bg-white border-0 text-center pb-4 pt-0">
                <a href="{{ url_for('index') }}" class="small text-muted text-decoration-none">
                    <i class="bi bi-arrow-left me-1"></i>Back to Home
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

files['templates/admin.html'] = """{% extends "base.html" %}

{% block title %}Feedback Dashboard - NLCF{% endblock %}

{% block extra_head %}
<style>
    .dashboard-header {
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        border-radius: var(--radius-lg);
        padding: 36px 40px;
        color: white;
        margin-bottom: 36px;
        box-shadow: var(--shadow-xl);
        position: relative;
        overflow: hidden;
    }
    .dashboard-header::after {
        content: '';
        position: absolute;
        top: -50%; right: -20%;
        width: 300px; height: 300px;
        background: rgba(255,255,255,0.04);
        border-radius: 50%;
    }
    .dashboard-header h1 { color: white; margin-bottom: 6px; }
    .dashboard-header p { opacity: 1; color: white; font-weight: 500; }

    .analytics-card {
        padding: 28px;
        height: 100%;
        border-radius: var(--radius-lg);
        background: white;
        box-shadow: var(--shadow-sm);
        border: 1px solid rgba(0,0,0,0.04);
    }
    .bar-item { margin-bottom: 18px; }
    .bar-item:last-child { margin-bottom: 0; }
    .bar-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 7px;
    }
    .bar-track {
        height: 8px;
        background: #f1f5f9;
        border-radius: 10px;
        overflow: hidden;
    }
    .bar-fill {
        height: 100%;
        border-radius: 10px;
        transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .action-btn {
        width: 34px; height: 34px;
        padding: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: all 0.2s;
        border: 1px solid #e2e8f0;
    }
    .action-btn:hover {
        background: #f1f5f9;
        transform: scale(1.05);
    }

    .rating-badge {
        font-size: 0.7rem;
        padding: 3px 10px;
        border-radius: 100px;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 48px;
    }
    .rating-Excellent { background: #d1fae5; color: #065f46; }
    .rating-Good { background: #dbeafe; color: #1e40af; }
    .rating-Fair { background: #fef3c7; color: #92400e; }
    .rating-Poor { background: #fee2e2; color: #991b1b; }

    .rating-mini-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .rating-mini-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        font-size: 0.78rem;
        padding: 6px 10px;
        background: #f8fafc;
        border-radius: 8px;
    }
    .rating-mini-item span:first-child {
        font-weight: 500;
        color: var(--text-muted);
    }

    .code-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 36px;
        height: 28px;
        padding: 0 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.78rem;
        font-family: 'JetBrains Mono', monospace;
        color: white;
    }
</style>
{% endblock %}

{% block content %}
<div class="dashboard-header animate-up">
    <div class="row align-items-center">
        <div class="col-md-7">
            <h1 class="fw-bold" style="font-size:clamp(1.4rem,3vw,2.2rem);">Feedback Dashboard</h1>
            <p class="mb-0">Review participant feedback from the 45th Annual Reunion.</p>
        </div>
        <div class="col-md-5 text-md-end mt-4 mt-md-0">
            <div class="d-flex gap-2 justify-content-md-end">
                <a href="{{ url_for('export') }}" class="btn btn-primary px-4">
                    <i class="bi bi-file-earmark-spreadsheet me-2"></i> Export Data
                </a>
            </div>
        </div>
    </div>
</div>

<div class="row g-4 mb-5">
    <div class="col-6 col-lg-3 animate-up" style="animation-delay: 0.05s">
        <div class="stat-card">
            <div class="stat-icon bg-primary-subtle text-primary">
                <i class="bi bi-chat-dots"></i>
            </div>
            <div class="stat-value">{{ total_feedback }}</div>
            <div class="stat-label">Total Feedback</div>
        </div>
    </div>
    <div class="col-6 col-lg-3 animate-up" style="animation-delay: 0.1s">
        <div class="stat-card">
            <div class="stat-icon bg-success-subtle text-success">
                <i class="bi bi-person-check"></i>
            </div>
            <div class="stat-value">{{ first_time_count }}</div>
            <div class="stat-label">First-Time Attendees</div>
        </div>
    </div>
    <div class="col-6 col-lg-3 animate-up" style="animation-delay: 0.15s">
        <div class="stat-card">
            <div class="stat-icon bg-warning-subtle text-warning">
                <i class="bi bi-person"></i>
            </div>
            <div class="stat-value">{{ age_dist.get('Below 18', 0) + age_dist.get('18-30', 0) + age_dist.get('31-45', 0) + age_dist.get('46-60', 0) + age_dist.get('61 and above', 0) }}</div>
            <div class="stat-label">Age Responses</div>
        </div>
    </div>
    <div class="col-6 col-lg-3 animate-up" style="animation-delay: 0.2s">
        <div class="stat-card">
            <div class="stat-icon bg-info-subtle text-info">
                <i class="bi bi-star"></i>
            </div>
            <div class="stat-value">{{ rating_data|length }}</div>
            <div class="stat-label">Rated Categories</div>
        </div>
    </div>
</div>

<div class="card glass-card border-0 mb-5 animate-up" style="animation-delay: 0.25s">
    <div class="card-body p-4">
        <form method="GET" action="{{ url_for('admin') }}">
            <div class="row g-3 align-items-end">
                <div class="col-lg-6 col-md-6">
                    <label class="form-label">Search</label>
                    <div class="input-group">
                        <span class="input-group-text bg-white border-end-0"><i class="bi bi-search"></i></span>
                        <input type="text" class="form-control border-start-0" name="search" placeholder="Name, Church, or Comments..." value="{{ search }}">
                    </div>
                </div>
                <div class="col-lg-4 col-md-10">
                    <div class="row g-2">
                        <div class="col-6">
                            <label class="form-label">Date From</label>
                            <input type="date" class="form-control" name="date_from" value="{{ date_from }}">
                        </div>
                        <div class="col-6">
                            <label class="form-label">Date To</label>
                            <input type="date" class="form-control" name="date_to" value="{{ date_to }}">
                        </div>
                    </div>
                </div>
                <div class="col-lg-2 col-md-2">
                    <label class="form-label" style="visibility:hidden;">Go</label>
                    <button type="submit" class="btn btn-primary w-100 p-2 rounded-pill"><i class="bi bi-funnel me-1"></i> Filter</button>
                </div>
            </div>
            {% if search or date_from or date_to %}
            <div class="mt-3">
                <a href="{{ url_for('admin') }}" class="btn btn-sm btn-outline-danger rounded-pill px-3">
                    <i class="bi bi-x-circle me-1"></i>Reset All Filters
                </a>
            </div>
            {% endif %}
        </form>
    </div>
</div>

<div class="row g-4 mb-5">
    <div class="col-lg-7 animate-up" style="animation-delay: 0.3s">
        <div class="card analytics-card border-0">
            <h5 class="fw-bold mb-4">Rating Distribution</h5>
            {% for item in rating_data %}
            <div class="bar-item">
                <div class="bar-label">
                    <span>{{ item.label }}</span>
                    <span class="text-muted small">E:{{ item.dist['Excellent'] }} G:{{ item.dist['Good'] }} F:{{ item.dist['Fair'] }} P:{{ item.dist['Poor'] }}</span>
                </div>
                {% set t = item.dist['Excellent'] + item.dist['Good'] + item.dist['Fair'] + item.dist['Poor'] %}
                <div class="d-flex gap-1" style="height: 10px;">
                    <div class="bar-fill bg-success" style="width: {{ (item.dist['Excellent'] / t * 100) if t > 0 else 0 }}%"></div>
                    <div class="bar-fill bg-primary" style="width: {{ (item.dist['Good'] / t * 100) if t > 0 else 0 }}%"></div>
                    <div class="bar-fill bg-warning" style="width: {{ (item.dist['Fair'] / t * 100) if t > 0 else 0 }}%"></div>
                    <div class="bar-fill bg-danger" style="width: {{ (item.dist['Poor'] / t * 100) if t > 0 else 0 }}%"></div>
                </div>
            </div>
            {% endfor %}
            <div class="d-flex gap-3 mt-3 small text-muted">
                <span><span class="badge bg-success">&nbsp;</span> Excellent</span>
                <span><span class="badge bg-primary">&nbsp;</span> Good</span>
                <span><span class="badge bg-warning">&nbsp;</span> Fair</span>
                <span><span class="badge bg-danger">&nbsp;</span> Poor</span>
            </div>
        </div>
    </div>
    <div class="col-lg-5 animate-up" style="animation-delay: 0.35s">
        <div class="card analytics-card border-0">
            <h5 class="fw-bold mb-4">Age Demographics</h5>
            {% for group in ['Below 18', '18-30', '31-45', '46-60', '61 and above'] %}
            {% set count = age_dist.get(group, 0) %}
            <div class="bar-item">
                <div class="bar-label">
                    <span>{{ group }}</span>
                    <span class="text-muted">{{ count }} Responses</span>
                </div>
                <div class="bar-track">
                    <div class="bar-fill bg-success" style="width: {{ (count / total_feedback * 100) if total_feedback > 0 else 0 }}%"></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<div class="animate-up" style="animation-delay: 0.4s">
    <div class="table-container">
        <div class="p-4 border-bottom d-flex justify-content-between align-items-center bg-white">
            <h5 class="fw-bold mb-0">Feedback Entries</h5>
            <span class="badge bg-light text-dark border">{{ feedbacks|length }} Records</span>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Name / Church</th>
                        <th>Age Group</th>
                        <th>Ratings</th>
                        <th>Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for fb in feedbacks %}
                    <tr style="cursor: pointer;" onclick="if(event.target.closest('.action-btn,form')) return; showFeedbackDetails('{{ fb.id }}')">
                        <td class="text-center"><span class="code-badge" style="background:var(--accent);">#{{ fb.id }}</span></td>
                        <td>
                            <div class="fw-bold" style="font-size:0.92rem;">{{ fb.name or 'Anonymous' }}</div>
                            <div class="small text-muted" style="font-size:0.78rem;">{{ fb.church_location or 'No church specified' }}</div>
                        </td>
                        <td><span class="badge bg-light text-dark rounded-pill px-3 py-1">{{ fb.age_group or '--' }}</span></td>
                        <td style="min-width:140px;">
                            <div class="rating-mini-grid">
                                {% if fb.rating_overall %}
                                <div class="rating-mini-item">
                                    <span>Overall</span>
                                    <span class="rating-badge rating-{{ fb.rating_overall }}">{{ fb.rating_overall }}</span>
                                </div>
                                {% endif %}
                                {% if not fb.rating_overall %}
                                <div class="rating-mini-item text-muted"><span>No ratings</span></div>
                                {% endif %}
                            </div>
                        </td>
                        <td>
                            <div style="font-size:0.85rem;font-weight:600;">{{ fb.submission_date|pht('%b %d, %Y') }}</div>
                            <div style="font-size:0.75rem;color:var(--text-muted);">{{ fb.submission_date|pht('%I:%M %p') }}</div>
                        </td>
                        <td>
                            <div class="d-flex gap-1" style="justify-content:center;">
                                <button class="btn btn-light action-btn" onclick="event.stopPropagation(); showFeedbackDetails('{{ fb.id }}')" title="View details">
                                    <i class="bi bi-eye" style="font-size:0.9rem;color:var(--accent);"></i>
                                </button>
                                <form method="POST" action="{{ url_for('delete_feedback', id=fb.id) }}" class="d-inline" onsubmit="return handleDelete(event, '{{ fb.id }}', '{{ fb.name or "Anonymous" }}')">
                                    <button type="submit" class="btn btn-light action-btn p-0 d-inline-flex" title="Delete">
                                        <i class="bi bi-trash" style="font-size:0.9rem;color:var(--danger);"></i>
                                    </button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% if not feedbacks %}
            <div class="p-5 text-center text-muted">
                <i class="bi bi-chat-square-text display-4 mb-3 d-block opacity-25"></i>
                No feedback entries found matching your criteria.
            </div>
            {% endif %}
        </div>
        {% if pagination.pages > 1 %}
        <div class="p-4 border-top d-flex justify-content-between align-items-center bg-white flex-wrap gap-3">
            <div class="small text-muted">
                Showing {{ pagination.per_page * (pagination.page - 1) + 1 }}&ndash;{{ pagination.per_page * (pagination.page - 1) + feedbacks|length }} of {{ pagination.total }} records
            </div>
            <nav>
                <ul class="pagination pagination-sm mb-0">
                    <li class="page-item {% if not pagination.has_prev %}disabled{% endif %}">
                        <a class="page-link rounded-pill" href="{{ url_for('admin', page=pagination.prev_num, search=search, date_from=date_from, date_to=date_to) if pagination.has_prev else '#' }}"><i class="bi bi-chevron-left"></i></a>
                    </li>
                    {% for page_num in pagination.iter_pages() %}
                    {% if page_num %}
                    <li class="page-item {% if page_num == pagination.page %}active{% endif %}">
                        <a class="page-link" href="{{ url_for('admin', page=page_num, search=search, date_from=date_from, date_to=date_to) }}">{{ page_num }}</a>
                    </li>
                    {% else %}
                    <li class="page-item disabled"><span class="page-link">...</span></li>
                    {% endif %}
                    {% endfor %}
                    <li class="page-item {% if not pagination.has_next %}disabled{% endif %}">
                        <a class="page-link rounded-pill" href="{{ url_for('admin', page=pagination.next_num, search=search, date_from=date_from, date_to=date_to) if pagination.has_next else '#' }}"><i class="bi bi-chevron-right"></i></a>
                    </li>
                </ul>
            </nav>
        </div>
        {% endif %}
    </div>
</div>

<div class="modal fade" id="feedbackDetailsModal" tabindex="-1">
    <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content border-0 shadow-xl">
            <div class="modal-header border-0 pb-0 p-4">
                <h5 class="fw-bold mb-0" id="fdName"></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body p-4 pt-2">
                <p class="small text-muted mb-3" id="fdChurch"></p>
                <div class="row g-3 mb-3">
                    <div class="col-4">
                        <div class="p-3 bg-light rounded-3">
                            <label class="small text-muted fw-bold d-block mb-1">Age Group</label>
                            <span class="fw-bold" id="fdAgeGroup"></span>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="p-3 bg-light rounded-3">
                            <label class="small text-muted fw-bold d-block mb-1">First Time?</label>
                            <span class="fw-bold" id="fdFirstTime"></span>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="p-3 bg-light rounded-3">
                            <label class="small text-muted fw-bold d-block mb-1">Date</label>
                            <span class="fw-bold" id="fdDate"></span>
                        </div>
                    </div>
                </div>
                <h6 class="fw-bold mb-2">Ratings</h6>
                <div class="row g-2 mb-3" id="fdRatings"></div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Most Impactful Part</h6>
                    <p class="mb-0" id="fdImpact"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Enjoyed Most</h6>
                    <p class="mb-0 text-muted" id="fdEnjoyed"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Areas for Improvement</h6>
                    <p class="mb-0 text-muted" id="fdImprove"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Announcements Clarity</h6>
                    <p class="mb-0" id="fdClarity"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Spiritual Impact</h6>
                    <p class="mb-1" id="fdFaith"></p>
                    <p class="mb-0 text-muted" id="fdLesson"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Connected to NLCF</h6>
                    <p class="mb-0" id="fdConnected"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Future Attendance</h6>
                    <p class="mb-0" id="fdFuture"></p>
                </div>
                <div class="mb-3">
                    <h6 class="fw-bold mb-2">Future Topics</h6>
                    <p class="mb-0 text-muted" id="fdTopics"></p>
                </div>
                <div class="mb-3" id="fdTestimonyDiv" style="display:none;">
                    <h6 class="fw-bold mb-2">Testimony</h6>
                    <div class="p-3 bg-light rounded-3">
                        <p class="mb-0 fst-italic" id="fdTestimony"></p>
                    </div>
                </div>
                <div class="mb-0">
                    <h6 class="fw-bold mb-2">Final Comments</h6>
                    <p class="mb-0 text-muted" id="fdComments"></p>
                </div>
            </div>
            <div class="modal-footer border-0 p-4 pt-0">
                <button type="button" class="btn btn-light" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function handleDelete(event, id, name) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: `Delete feedback #${id} from ${name}?`,
        text: "This action cannot be undone.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Yes, delete it!'
    }).then((result) => {
        if (result.isConfirmed) form.submit();
    });
    return false;
}

function showFeedbackDetails(id) {
    fetch(`/nlcfadmin.SystemAdmin/feedback/${id}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('fdName').textContent = data.name || 'Anonymous';
            document.getElementById('fdChurch').textContent = data.church_location || 'No church specified';
            document.getElementById('fdAgeGroup').textContent = data.age_group || '--';
            document.getElementById('fdFirstTime').textContent = data.first_time_attending || '--';
            document.getElementById('fdDate').textContent = data.submission_date || '--';
            document.getElementById('fdImpact').textContent = data.most_impactful_part || '--';
            if (data.most_impactful_other) {
                document.getElementById('fdImpact').textContent += ' (' + data.most_impactful_other + ')';
            }
            document.getElementById('fdEnjoyed').textContent = data.enjoyed_most || 'No response';
            document.getElementById('fdImprove').textContent = data.areas_for_improvement || 'No response';
            document.getElementById('fdClarity').textContent = data.announcements_clarity || '--';
            document.getElementById('fdFaith').textContent = data.faith_strengthened || '--';
            document.getElementById('fdLesson').textContent = data.spiritual_lesson || '';
            document.getElementById('fdConnected').textContent = data.connected_to_nlcf || '--';
            document.getElementById('fdFuture').textContent = data.attend_future || '--';
            document.getElementById('fdTopics').textContent = data.future_topics || 'No response';
            document.getElementById('fdComments').textContent = data.final_comments || 'No response';

            const testimonyDiv = document.getElementById('fdTestimonyDiv');
            if (data.testimony) {
                testimonyDiv.style.display = 'block';
                document.getElementById('fdTestimony').textContent = data.testimony;
            } else {
                testimonyDiv.style.display = 'none';
            }

            const rc = document.getElementById('fdRatings');
            const rm = data.ratings || {};
            let html = '';
            for (const [label, rating] of Object.entries(rm)) {
                html += `<div class="col-6"><div class="d-flex justify-content-between p-2 bg-light rounded-3 small"><span>${label}</span><span class="rating-badge rating-${rating}">${rating}</span></div></div>`;
            }
            rc.innerHTML = html || '<div class="col-12 text-muted small">No ratings provided</div>';

            new bootstrap.Modal(document.getElementById('feedbackDetailsModal')).show();
        });
}
</script>
{% endblock %}
"""

files['templates/feedback_thankyou.html'] = """{% extends "base.html" %}

{% block title %}Thank You - NLCF Feedback{% endblock %}

{% block extra_head %}
<style>
    .thankyou-wrapper {
        min-height: calc(100vh - var(--nav-height) - 200px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px 0;
    }
    .thankyou-card {
        animation: scaleIn 0.5s ease;
    }
    .success-check {
        width: 90px; height: 90px;
        background: linear-gradient(135deg, var(--success), #059669);
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 2.8rem;
        margin: 0 auto 24px;
        box-shadow: 0 0 40px rgba(16, 185, 129, 0.3);
    }
    .thanks-glow {
        position: relative;
    }
    .thanks-glow::after {
        content: '';
        position: absolute;
        top: -20px; left: 50%;
        transform: translateX(-50%);
        width: 120px; height: 120px;
        background: radial-gradient(circle, rgba(16,185,129,0.1) 0%, transparent 70%);
        border-radius: 50%;
        pointer-events: none;
    }
</style>
{% endblock %}

{% block content %}
<div class="thankyou-wrapper">
    <div class="col-md-8 col-lg-6 thankyou-card">
        <div class="card border-0 shadow-lg text-center p-4 p-md-5 position-relative overflow-hidden">
            <div class="thanks-glow">
                <div class="success-check mx-auto">
                    <i class="bi bi-check-lg"></i>
                </div>
            </div>
            <h2 class="fw-bold mb-3">Thank You!</h2>
            <p class="text-muted mb-3" style="font-size: 1.1rem; max-width: 400px; margin: 0 auto;">
                Your feedback has been recorded. We truly appreciate you taking the time to share your thoughts.
            </p>
            <div class="d-flex flex-wrap gap-3 justify-content-center mt-4">
                <a href="{{ url_for('feedback') }}" class="btn btn-primary px-4 rounded-pill">
                    <i class="bi bi-pencil me-2"></i>Submit Another
                </a>
                <a href="{{ url_for('index') }}" class="btn btn-outline-primary px-4 rounded-pill">
                    <i class="bi bi-house me-2"></i>Return Home
                </a>
            </div>
            <div class="mt-4 pt-3 border-top">
                <p class="text-muted fst-italic mb-0 small">&ldquo;To God be all the glory!&rdquo;</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

files['static/css/style.css'] = """:root {
    --primary: #0f172a;
    --primary-light: #1e293b;
    --accent: #556B2F;
    --accent-soft: #6d8a3e;
    --accent-glow: rgba(85, 107, 47, 0.25);
    --secondary: #6B8E23;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --bg-main: #f0f2f5;
    --bg-card: #ffffff;
    --text-main: #0f172a;
    --text-sub: #334155;
    --text-muted: #64748b;
    --text-light: #94a3b8;
    --glass-bg: rgba(255, 255, 255, 0.82);
    --glass-border: rgba(255, 255, 255, 0.35);
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
    --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.06);
    --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.08);
    --shadow-xl: 0 24px 48px rgba(0, 0, 0, 0.12);
    --bs-primary: #556B2F;
    --bs-primary-rgb: 85, 107, 47;
    --bs-primary-bg-subtle: #e8edd9;
    --bs-link-color: #556B2F;
    --bs-link-hover-color: #3d5a1e;
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 20px;
    --radius-xl: 28px;
    --nav-height: 72px;
    --font-scale: 1.125;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

::selection { background: var(--accent); color: white; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

html { font-size: 16px; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-weight: 400;
    background-color: var(--bg-main);
    color: var(--text-main);
    line-height: 1.65;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
}

body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background:
        linear-gradient(135deg, rgba(248,250,252,0.92) 0%, rgba(248,250,252,0.86) 100%),
        url('../img/Logo.jpg') no-repeat center/cover;
    filter: blur(6px);
    -webkit-filter: blur(6px);
    transform: scale(1.1);
    z-index: -1;
    pointer-events: none;
}

body::after {
    content: '';
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background:
        radial-gradient(ellipse at 20% 50%, rgba(85,107,47,0.04) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 50%, rgba(107,142,35,0.03) 0%, transparent 60%);
    z-index: -1;
    pointer-events: none;
}

/* TYPOGRAPHY SCALE */

h1, h2, h3, h4, h5, h6 {
    font-weight: 700;
    letter-spacing: -0.025em;
    color: var(--text-main);
    line-height: 1.25;
}

h1 { font-size: clamp(1.6rem, 4.5vw, 2.6rem); font-weight: 800; letter-spacing: -0.03em; }
h2 { font-size: clamp(1.35rem, 3.5vw, 1.95rem); font-weight: 700; }
h3 { font-size: clamp(1.15rem, 2.5vw, 1.5rem); font-weight: 700; }
h4 { font-size: clamp(1.05rem, 2vw, 1.25rem); font-weight: 700; }
h5 { font-size: 1.05rem; font-weight: 700; }
h6 { font-size: 0.95rem; font-weight: 700; }

p { margin-bottom: 0.75rem; color: var(--text-sub); }

small, .small { font-size: 0.82rem; }

.text-gradient {
    background: linear-gradient(135deg, var(--text-main) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.text-accent { color: var(--accent); }
.text-subtle { color: var(--text-muted); }

.lead {
    font-size: 1.1rem;
    font-weight: 400;
    line-height: 1.6;
    color: var(--text-sub);
}

/* NAVIGATION */

.navbar {
    height: var(--nav-height);
    background: var(--glass-bg);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border-bottom: 1px solid var(--glass-border);
    box-shadow: 0 1px 8px rgba(0,0,0,0.04);
}

.navbar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    font-weight: 700;
    color: var(--primary) !important;
    font-size: 1.1rem;
    letter-spacing: -0.02em;
}

.navbar-brand img {
    height: 38px; width: 38px;
    border-radius: 10px;
    object-fit: cover;
    box-shadow: var(--shadow-sm);
}

.nav-link {
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text-muted) !important;
    padding: 7px 18px !important;
    border-radius: 100px;
    transition: all 0.25s ease;
    letter-spacing: -0.01em;
}

.nav-link:hover {
    color: var(--accent) !important;
    background: rgba(85, 107, 47, 0.08);
}

.nav-link.active {
    color: white !important;
    font-weight: 600;
    background: linear-gradient(135deg, var(--accent), var(--secondary));
    box-shadow: 0 2px 10px rgba(85,107,47,0.3);
}

/* CARDS */

.card {
    background: white;
    border: none;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    overflow: hidden;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
}

.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    box-shadow: var(--shadow-lg);
}

/* BUTTONS */

.btn {
    padding: 11px 26px;
    font-weight: 600;
    font-size: 0.92rem;
    border-radius: 100px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: none;
    letter-spacing: -0.01em;
}

.btn-primary {
    background: linear-gradient(135deg, var(--accent) 0%, var(--secondary) 100%);
    color: white;
    box-shadow: 0 4px 16px rgba(85, 107, 47, 0.3);
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(85, 107, 47, 0.35);
    background: linear-gradient(135deg, var(--accent) 10%, var(--secondary) 120%);
}

.btn-primary:active { transform: translateY(0); }

.btn-outline-primary {
    border: 2px solid var(--accent);
    color: var(--accent);
    background: transparent;
}

.btn-outline-primary:hover {
    background: var(--accent);
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(85,107,47,0.2);
}

.btn-light {
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: var(--text-main);
    font-weight: 500;
}

.btn-light:hover {
    background: #e2e8f0;
    transform: translateY(-1px);
}

.btn-lg { padding: 14px 34px; font-size: 1rem; }

/* FORMS */

.form-label {
    font-weight: 600;
    color: var(--text-sub);
    margin-bottom: 6px;
    font-size: 0.85rem;
    letter-spacing: -0.01em;
}

.form-control, .form-select {
    padding: 12px 16px;
    border-radius: var(--radius-md);
    border: 1.5px solid #e2e8f0;
    background-color: #fafbfc;
    transition: all 0.25s ease;
    font-size: 0.92rem;
    font-family: 'Inter', sans-serif;
    color: var(--text-main);
}

.form-control::placeholder {
    color: var(--text-light);
    font-weight: 400;
}

.form-control:hover, .form-select:hover {
    border-color: #cbd5e1;
    background-color: white;
}

.form-control:focus, .form-select:focus {
    background-color: white;
    border-color: var(--accent);
    box-shadow: 0 0 0 4px var(--accent-glow);
    outline: none;
}

textarea.form-control {
    resize: vertical;
    min-height: 80px;
    line-height: 1.6;
}

.input-group-text {
    font-size: 0.9rem;
    color: var(--text-muted);
    border-color: #e2e8f0;
}

/* STAT CARDS */

.stat-card {
    position: relative;
    padding: 24px 26px;
    border-radius: var(--radius-lg);
    background: white;
    border: 1px solid rgba(0, 0, 0, 0.04);
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: var(--shadow-sm);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    overflow: hidden;
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--secondary));
    opacity: 0.6;
}

.stat-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
}

.stat-icon {
    width: 48px; height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    flex-shrink: 0;
}

.stat-icon.bg-primary-subtle { background: #e8edd9; color: var(--accent); }
.stat-icon.bg-success-subtle { background: #d1fae5; color: #065f46; }
.stat-icon.bg-warning-subtle { background: #fef3c7; color: #92400e; }
.stat-icon.bg-info-subtle { background: #dbeafe; color: #1e40af; }

.stat-value {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--text-main);
    line-height: 1.1;
    letter-spacing: -0.03em;
}

.stat-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* TABLES */

.table-container {
    border-radius: var(--radius-lg);
    background: white;
    box-shadow: var(--shadow-md);
    overflow: hidden;
    border: 1px solid rgba(0,0,0,0.04);
}

.table { margin-bottom: 0; }

.table thead th {
    background: #f8fafc;
    color: var(--text-muted);
    font-weight: 700;
    text-transform: uppercase;
    font-size: 0.65rem;
    letter-spacing: 0.08em;
    padding: 16px 20px;
    border-bottom: 2px solid #e2e8f0;
}

.table tbody td {
    padding: 14px 20px;
    vertical-align: middle;
    color: var(--text-main);
    font-size: 0.9rem;
    border-bottom: 1px solid #f1f5f9;
}

.table tbody tr:last-child td { border-bottom: none; }
.table tbody tr:hover { background-color: #f8fafc; }
.table tbody tr { transition: background 0.15s ease; }

/* ANIMATIONS */

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes scaleIn {
    from { opacity: 0; transform: scale(0.95); }
    to { opacity: 1; transform: scale(1); }
}

.animate-up {
    animation: fadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

.animate-in {
    animation: fadeIn 0.4s ease forwards;
}

/* SUCCESS CHECK */

.success-check {
    width: 80px; height: 80px;
    background: linear-gradient(135deg, var(--success), #059669);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.4rem;
    margin: 0 auto 24px;
    box-shadow: 0 0 30px rgba(16, 185, 129, 0.3);
    animation: scaleIn 0.4s ease;
}

/* FOOTER */

footer {
    margin-top: auto;
    padding: 28px 0;
    background: white;
    border-top: 1px solid #e2e8f0;
}

.footer-text {
    color: var(--text-muted);
    font-size: 0.82rem;
}

/* PAGINATION */

.pagination { gap: 4px; }

.page-link {
    border: 1px solid #e2e8f0;
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.8rem;
    padding: 6px 12px;
    border-radius: 8px !important;
    transition: all 0.2s ease;
}

.page-link:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
    color: var(--accent);
}

.page-item.active .page-link {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
    box-shadow: 0 2px 8px rgba(85,107,47,0.25);
}

.page-item.disabled .page-link { opacity: 0.4; }

/* MODAL */

.modal-content {
    border: none;
    border-radius: var(--radius-lg);
    box-shadow: 0 25px 60px rgba(0,0,0,0.15);
}

.modal-header { border-bottom-color: #f1f5f9; }
.modal-footer { border-top-color: #f1f5f9; }

/* ALERTS */

.alert {
    border-radius: var(--radius-md);
    padding: 14px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-left: 4px solid currentColor;
    font-size: 0.92rem;
}

.alert-success { border-left-color: var(--success); color: #065f46; }
.alert-danger { border-left-color: var(--danger); color: #991b1b; }
.alert-warning { border-left-color: var(--warning); color: #92400e; }
.alert-info { border-left-color: #3b82f6; color: #1e40af; }

/* BADGES */

.badge {
    font-weight: 500;
    font-size: 0.78rem;
    letter-spacing: -0.01em;
}

.badge.rounded-pill {
    padding: 4px 14px;
    font-weight: 600;
}

.code-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 36px;
    height: 26px;
    padding: 0 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.75rem;
    font-feature-settings: 'tnum' 1;
    color: white;
}

/* RESPONSIVE */

@media (max-width: 768px) {
    :root { --nav-height: 60px; }
    .navbar-brand { font-size: 0.95rem; }
    .navbar-brand img { height: 30px; width: 30px; border-radius: 8px; }
    .card { border-radius: var(--radius-md); }
    .stat-card { padding: 18px 20px; }
    .stat-value { font-size: 1.4rem; }
    .stat-icon { width: 42px; height: 42px; font-size: 1.1rem; }
    .table thead th { padding: 12px 14px; font-size: 0.6rem; }
    .table tbody td { padding: 12px 14px; font-size: 0.85rem; }
    .btn { padding: 9px 20px; font-size: 0.85rem; }
    .btn-lg { padding: 12px 26px; font-size: 0.92rem; }
    .form-control, .form-select { font-size: 0.88rem; padding: 10px 14px; }
    .form-label { font-size: 0.82rem; }
}
"""


def main():
    for relpath, content in files.items():
        abspath = os.path.join(BASE, relpath)
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        with open(abspath, 'w') as f:
            f.write(content)
        print(f"Wrote {abspath}")

if __name__ == '__main__':
    main()
