# app.py - Hauptanwendung mit Flask
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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

# Routen
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    today = datetime.today()
    today_lessons = Lesson.query.filter(Lesson.date == today.date()).all()
    courses = Course.query.filter_by(teacher_id=user.id).all()
    
    return render_template('index.html',
                         user=user,  # Wichtig: user an Template übergeben
                         courses=courses,
                         today_lessons=today_lessons)

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

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.date).all()
    return render_template('course.html', course=course, lessons=lessons)

@app.route('/lesson/<int:lesson_id>', methods=['GET', 'POST'])
def lesson_detail(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    if request.method == 'POST':
        # Speichere die Eingaben
        lesson.plan_field1 = request.form['plan_field1']
        lesson.field2 = request.form['field2']
        lesson.plan_field3 = request.form['plan_field3']
        db.session.commit()
        flash('Lektion gespeichert!')
        
        # Übertrage Planung für nächsten Tag
        next_lesson = Lesson.query.filter(
            Lesson.course_id == lesson.course_id,
            Lesson.date > lesson.date
        ).order_by(Lesson.date.asc()).first()
        
        if next_lesson:
            next_lesson.plan_field1 = lesson.plan_field3
            db.session.commit()
    
    return render_template('lesson.html', lesson=lesson)

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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)