# app.py - Hauptanwendung mit Flask
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import make_response
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask import send_file

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(basedir, 'templates'))
app.secret_key = 'geheimes_schluesselwort'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
db = SQLAlchemy(app)

# Datenbankmodelle
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    courses = db.relationship('Course', backref='teacher', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lessons = db.relationship('Lesson', backref='course', lazy=True)
    participants = db.relationship('Participant', backref='course', lazy=True)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(200))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    plan_field1 = db.Column(db.Text)  # Planung für heute
    field2 = db.Column(db.Text)       # Durchgeführtes
    plan_field3 = db.Column(db.Text)  # Planung für nächsten Tag
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    attendance = db.relationship('Attendance', backref='lesson', lazy=True, cascade="all, delete-orphan")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    status = db.Column(db.String(20))  # anwesend, abwesend, verspätet, verfrüht
    minutes_missed = db.Column(db.Integer, default=0)
    note = db.Column(db.String(200))

# Routen
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    # Datumsfilter
    selected_date = datetime.today().date()
    if request.method == 'POST':
        date_str = request.form.get('date')
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    elif request.args.get('date'):
        date_str = request.args.get('date')
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Kurse des Benutzers
    courses = Course.query.filter_by(teacher_id=user.id).all()
    
    # Lektionen für das ausgewählte Datum
    selected_lessons = Lesson.query.filter(
        Lesson.course_id.in_([c.id for c in courses]),
        Lesson.date == selected_date
    ).all()
    
    # Heutige Lektionen (für den Standard-View)
    today_lessons = Lesson.query.filter(
        Lesson.course_id.in_([c.id for c in courses]),
        Lesson.date == datetime.today().date()
    ).all()
    
    return render_template('index.html',
                         user=user,
                         courses=courses,
                         today_lessons=today_lessons,
                         selected_lessons=selected_lessons,
                         selected_date=selected_date.strftime('%Y-%m-%d'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            return redirect(url_for('home'))
        else:
            flash('Falscher Benutzername oder Passwort')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Session leeren
    flash('Sie wurden erfolgreich ausgeloggt')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Benutzername existiert bereits')
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Konto erfolgreich erstellt!')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/course/<int:course_id>', methods=['GET', 'POST'])
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.date).all()
    
    # Neue Teilnehmer hinzufügen
    if request.method == 'POST':
        name = request.form.get('name')
        contact = request.form.get('contact', '')
        
        if name:
            participant = Participant(name=name, contact=contact, course_id=course_id)
            db.session.add(participant)
            db.session.commit()
            flash('Teilnehmer hinzugefügt!')
            return redirect(url_for('course_detail', course_id=course_id))
    
    return render_template('course.html', course=course, lessons=lessons)

@app.route('/lesson/<int:lesson_id>', methods=['GET', 'POST'])
def lesson_detail(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    participants = Participant.query.filter_by(course_id=lesson.course_id).all()
    
    if request.method == 'POST':
        # Speichere die Eingaben
        lesson.plan_field1 = request.form['plan_field1']
        lesson.field2 = request.form['field2']
        lesson.plan_field3 = request.form['plan_field3']
        db.session.commit()
        flash('Lektion gespeichert!')
        
        # Anwesenheiten speichern
        for participant in participants:
            status = request.form.get(f'status_{participant.id}')
            minutes = request.form.get(f'minutes_{participant.id}', 0)
            note = request.form.get(f'note_{participant.id}', '')
            
            attendance = Attendance.query.filter_by(
                lesson_id=lesson_id,
                participant_id=participant.id
            ).first()
            
            if not attendance:
                attendance = Attendance(
                    lesson_id=lesson_id,
                    participant_id=participant.id
                )
                db.session.add(attendance)
            
            attendance.status = status
            attendance.minutes_missed = int(minutes) if minutes else 0
            attendance.note = note
        
        db.session.commit()
        flash('Lektion und Anwesenheiten gespeichert!')

        # Übertrage Planung für nächsten Tag
        next_lesson = Lesson.query.filter(
            Lesson.course_id == lesson.course_id,
            Lesson.date > lesson.date
        ).order_by(Lesson.date.asc()).first()
        
        if next_lesson:
            next_lesson.plan_field1 = lesson.plan_field3
            db.session.commit()
    
    # Vorhandene Anwesenheiten laden
    attendance_data = {}
    for a in lesson.attendance:
        attendance_data[a.participant_id] = {
            'status': a.status,
            'minutes_missed': a.minutes_missed,
            'note': a.note
        }
    
    return render_template('lesson.html', 
                          lesson=lesson, 
                          participants=participants,
                          attendance_data=attendance_data)

@app.route('/create_course', methods=['POST'])
def create_course():
    title = request.form['title']
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
    
    new_course = Course(
        title=title,
        start_date=start_date,
        end_date=end_date,
        teacher_id=session['user_id']
    )
    
    db.session.add(new_course)
    db.session.commit()
    return redirect(url_for('home'))

@app.template_filter('format_date')
def format_date_filter(date_str):
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        return date.strftime('%d.%m.%Y')
    except:
        return date_str

@app.route('/course_journal/<int:course_id>')
def course_journal(course_id):
    course = Course.query.get_or_404(course_id)
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.date).all()
    
    # PDF in Memory erstellen
    buffer = BytesIO()
    
    # PDF-Inhalt generieren
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Titel
    title = Paragraph(f"Kurstagebuch: {course.title}", styles['Title'])
    story.append(title)
    
    # Kursinformationen
    info = Paragraph(
        f"<b>Start:</b> {course.start_date.strftime('%d.%m.%Y')}<br/>"
        f"<b>Ende:</b> {course.end_date.strftime('%d.%m.%Y')}<br/><br/>",
        styles['Normal']
    )
    story.append(info)
    
    # Lektionsinhalte
    for lesson in lessons:
        date_str = lesson.date.strftime('%d.%m.%Y')
        content = Paragraph(
            f"<b>{date_str}:</b><br/>"
            f"{lesson.field2 or 'Keine Dokumentation vorhanden'}<br/><br/>",
            styles['Normal']
        )
        story.append(content)
    
    doc.build(story)
    
    # Buffer zurücksetzen und als PDF senden
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Kurstagebuch_{course.title}.pdf",
        mimetype='application/pdf'
    )

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)