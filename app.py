from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pandas as pd
import io
import os
import logging

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
    'age_group', 'first_time_attending', 'participant_category',
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
        'submission_date': fb.submission_date.strftime('%b %d, %Y %I:%M %p') if fb.submission_date else ''
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
                'Submission Date': fb.submission_date.strftime('%Y-%m-%d %H:%M:%S') if fb.submission_date else ''
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
            download_name=f'feedback_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'Export error: {str(e)}')
        flash('An error occurred during export.', 'danger')
        return redirect(url_for('admin'))


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat(), 'version': 1})


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
