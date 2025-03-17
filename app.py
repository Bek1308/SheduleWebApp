from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime, timedelta
from auth import init_users_db, register, login  # auth.py dan import

app = Flask(__name__)
app.secret_key = 'supersecretkey123'  # Sessiya va flash xabarlari uchun

RESOURCES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Resources')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schedules.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_migration_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'")
    table_exists = cursor.fetchone()
    if table_exists:
        cursor.execute("SELECT COUNT(*) FROM schedules")
        count = cursor.fetchone()[0]
    else:
        count = 0
    conn.close()
    return count > 0

def migrate_to_sqlite():
    if check_migration_status():
        print("ℹ️ Ma'lumotlar bazasi allaqachon to‘ldirilgan. Migratsiya o‘tkazilmaydi.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty TEXT NOT NULL,
        course TEXT NOT NULL,
        "group" TEXT NOT NULL,
        day TEXT NOT NULL,
        lesson_time TEXT,
        lesson_type TEXT,
        subject TEXT,
        teacher TEXT,
        room TEXT
    )''')

    for faculty in os.listdir(RESOURCES_PATH):
        faculty_path = os.path.join(RESOURCES_PATH, faculty)
        if not os.path.isdir(faculty_path):
            continue
        for course in os.listdir(faculty_path):
            course_path = os.path.join(faculty_path, course)
            if not os.path.isdir(course_path):
                continue
            for group_file in os.listdir(course_path):
                if group_file.endswith('.txt'):
                    group = group_file[:-4]
                    with open(os.path.join(course_path, group_file), 'r', encoding='utf-8') as f:
                        content = f.read()
                    schedule = parse_schedule(content)
                    for day, data in schedule.items():
                        for lesson in data['lessons']:
                            cursor.execute('''INSERT INTO schedules 
                                (faculty, course, "group", day, lesson_time, lesson_type, subject, teacher, room)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (faculty, course, group, day.split()[0], lesson['time'], 
                                 lesson['type'], lesson['subject'], lesson['teacher'], lesson['room']))
    conn.commit()
    conn.close()
    print("✅ Migratsiya muvaffaqiyatli yakunlandi.")

DAYS_OF_WEEK = ["Душанбе", "Сешанбе", "Чоршанбе", "Панҷшанбе", "Ҷумъа", "Шанбе", "Якшанбе"]

def get_current_week_dates():
    today = datetime.now()
    week_dates = {}
    for i in range(7):  # Bugundan boshlab 7 kun
        target_date = today + timedelta(days=i)
        weekday_num = target_date.weekday()
        day_name = DAYS_OF_WEEK[weekday_num]
        week_dates[day_name] = target_date.strftime("%d.%m.%Y")
    return week_dates

def parse_schedule(content):
    schedule = {}
    current_day = None
    file_schedule = {}
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        if any(day.lower() in line.lower() for day in DAYS_OF_WEEK):
            for day in DAYS_OF_WEEK:
                if day.lower() in line.lower():
                    current_day = day
                    file_schedule[current_day] = []
                    break
        elif current_day:
            parts = line.split('|')
            if len(parts) >= 5:
                lesson = {
                    'subject': parts[0].strip(),
                    'type': parts[1].strip(),
                    'teacher': parts[2].strip(),
                    'time': parts[3].strip(),
                    'room': parts[4].strip()
                }
                file_schedule[current_day].append(lesson)
    
    for day in DAYS_OF_WEEK:
        schedule[day] = {'date': '', 'weekday': DAYS_OF_WEEK.index(day), 'lessons': file_schedule.get(day, [])}
    return schedule

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('main'))  # Tizimga kirgan bo‘lsa main sahifasiga o‘tadi
    return render_template('index1.html')

@app.route('/main')
def main():
    if 'username' not in session:
        flash('Sizda tizimga kirishga ruxsat yo‘q! Iltimos, avval tizimga kiring.', 'danger')
        return redirect(url_for('login'))
    return render_template('main.html', username=session['username'], is_admin=session.get('is_admin', 0))

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    return login()  # auth.py dan login funksiyasini chaqiramiz

@app.route('/register', methods=['GET', 'POST'])
def register_route():
    return register()  # auth.py dan register funksiyasini chaqiramiz

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    flash('Tizimdan muvaffaqiyatli chiqdingiz!', 'success')
    return redirect(url_for('index'))

@app.route('/get_faculties')
def get_faculties():
    conn = get_db_connection()
    faculties = conn.execute('SELECT DISTINCT faculty FROM schedules').fetchall()
    conn.close()
    return jsonify([f['faculty'] for f in faculties])

@app.route('/get_courses')
def get_courses():
    faculty = request.args.get('faculty')
    conn = get_db_connection()
    courses = conn.execute('SELECT DISTINCT course FROM schedules WHERE faculty=?', (faculty,)).fetchall()
    conn.close()
    return jsonify([c['course'] for c in courses])

@app.route('/get_groups')
def get_groups():
    faculty = request.args.get('faculty')
    course = request.args.get('course')
    conn = get_db_connection()
    groups = conn.execute('SELECT DISTINCT "group" FROM schedules WHERE faculty=? AND course=?', 
                         (faculty, course)).fetchall()
    conn.close()
    return jsonify([g['group'] for g in groups])

@app.route('/<faculty>/<course>/<group>')
def show_schedule(faculty, course, group):
    # if 'username' not in session:
    #     flash('Sizda bu sahifani ko‘rishga ruxsat yo‘q! Iltimos, tizimga kiring.', 'danger')
    #     return redirect(url_for('login'))
    
    day = request.args.get('day')
    conn = get_db_connection()
    if day:
        lessons = conn.execute('SELECT * FROM schedules WHERE faculty=? AND course=? AND "group"=? AND LOWER(day)=LOWER(?)',
                              (faculty, course, group, day)).fetchall()
    else:
        lessons = conn.execute('SELECT * FROM schedules WHERE faculty=? AND course=? AND "group"=?',
                              (faculty, course, group)).fetchall()
    conn.close()

    schedule = {}
    week_dates = get_current_week_dates()  # Bugundan boshlab sanalar
    ordered_days = list(week_dates.keys())  # Bugungi kundan boshlab tartib
    for day_name in ordered_days:
        schedule[day_name] = {
            'date': week_dates[day_name],
            'weekday': DAYS_OF_WEEK.index(day_name),
            'lessons': []
        }
    for lesson in lessons:
        day_name = lesson['day']
        if day_name in schedule:
            schedule[day_name]['lessons'].append({
                'time': lesson['lesson_time'],
                'type': lesson['lesson_type'],
                'subject': lesson['subject'],
                'teacher': lesson['teacher'],
                'room': lesson['room']
            })

    return render_template('schedule.html', schedule=schedule, group=f"{faculty} | {course} | {group}-гуруҳ", day=day)

@app.route('/get_day/<faculty>/<course>/<group>')
def get_day_schedule(faculty, course, group):
    # Tizimga kirish talabi olib tashlandi, Telegram foydalanuvchilari uchun ochiq
    day = request.args.get('day')
    conn = get_db_connection()
    lessons = conn.execute('SELECT * FROM schedules WHERE faculty=? AND course=? AND "group"=? AND LOWER(day)=LOWER(?)',
                          (faculty, course, group, day)).fetchall()
    conn.close()
    
    if not lessons and day != "Якшанбе":
        return f"❌ Дар ин рӯз ({day}) барои гуруҳи--{group}  жадвали дарсӣ вуҷуд надорад!"
    elif day == "Якшанбе":
        return f"📅 {day} - {faculty} | {course} | {group}-гуруҳ\n\n❌ Дар ин рузи жадвали дарсӣ вуҷуд надорад!"
    
    response = f"📅 {day} - {faculty} | {course} | {group}-гуруҳ\n\n"
    for lesson in lessons:
        response += f"⏰ {lesson['lesson_time']}\n🔖 {lesson['lesson_type']}\n📌 {lesson['subject']}\n👨‍🏫 {lesson['teacher']}\n🏫 {lesson['room']}\n\n"
    return response

    
@app.route('/pages/<page_name>')
def load_page(page_name):
    try:
        return render_template(f'{page_name}.html')
    except:
        return "<h1>Xato</h1><p>Sahifa topilmadi!</p>", 404

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    # if 'username' not in session:
    #     flash('Sizda admin paneliga kirishga ruxsat yo‘q! Iltimos, tizimga kiring.', 'danger')
    #     return redirect(url_for('login'))
    
    # if not session.get('is_admin', 0):
    #     flash('Sizda admin huquqlari yo‘q! Faqat administratorlar bu sahifaga kirishi mumkin.', 'danger')
    #     return redirect(url_for('main'))
    
    conn = get_db_connection()
    faculties = conn.execute('SELECT DISTINCT faculty FROM schedules').fetchall()
    conn.close()

    selected_faculty = request.args.get('faculty', '')
    selected_course = request.args.get('course', '')
    selected_group = request.args.get('group', '')

    courses = []
    groups = []
    schedules = {}
    week_dates = get_current_week_dates()
    ordered_days = list(week_dates.keys())  # Bugungi kundan boshlab tartib

    if selected_faculty:
        conn = get_db_connection()
        courses = conn.execute('SELECT DISTINCT course FROM schedules WHERE faculty=?', (selected_faculty,)).fetchall()
        conn.close()

    if selected_faculty and selected_course:
        conn = get_db_connection()
        groups = conn.execute('SELECT DISTINCT "group" FROM schedules WHERE faculty=? AND course=?', 
                             (selected_faculty, selected_course)).fetchall()
        conn.close()

    if selected_faculty and selected_course and selected_group:
        conn = get_db_connection()
        lessons = conn.execute('SELECT * FROM schedules WHERE faculty=? AND course=? AND "group"=?',
                              (selected_faculty, selected_course, selected_group)).fetchall()
        conn.close()
        for day_name in ordered_days:
            schedules[day_name] = []
        for lesson in lessons:
            day = lesson['day']
            if day in schedules:
                schedules[day].append(lesson)

    return render_template('admin.html', 
                          faculties=faculties, 
                          courses=courses, 
                          groups=groups, 
                          schedules=schedules,
                          selected_faculty=selected_faculty,
                          selected_course=selected_course,
                          selected_group=selected_group,
                          days=ordered_days,  # Tartiblangan kunlar
                          week_dates=week_dates)

@app.route('/admin/add', methods=['POST'])
def add_schedule():
    if 'username' not in session or not session.get('is_admin', 0):
        flash('Sizda bu amalni bajarishga ruxsat yo‘q!', 'danger')
        return redirect(url_for('main'))
    
    conn = get_db_connection()
    faculty = request.form['faculty']
    course = request.form['course']
    group = request.form['group']
    day = request.form['day']
    lesson_time = request.form['lesson_time']
    lesson_type = request.form['lesson_type']
    subject = request.form['subject']
    teacher = request.form['teacher']
    room = request.form['room']
    
    conn.execute('INSERT INTO schedules (faculty, course, "group", day, lesson_time, lesson_type, subject, teacher, room) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (faculty, course, group, day, lesson_time, lesson_type, subject, teacher, room))
    conn.commit()
    conn.close()
    flash('Jadval muvaffaqiyatli qo‘shildi!', 'success')
    return redirect(url_for('admin_panel', faculty=faculty, course=course, group=group))

@app.route('/admin/update/<int:id>', methods=['POST'])
def update_schedule(id):
    if 'username' not in session or not session.get('is_admin', 0):
        return jsonify({'status': 'error', 'message': 'Sizda bu amalni bajarishga ruxsat yo‘q!'})
    
    conn = get_db_connection()
    faculty = request.form['faculty']
    course = request.form['course']
    group = request.form['group']
    day = request.form['day']
    lesson_time = request.form['lesson_time']
    lesson_type = request.form['lesson_type']
    subject = request.form['subject']
    teacher = request.form['teacher']
    room = request.form['room']
    
    conn.execute('UPDATE schedules SET faculty=?, course=?, "group"=?, day=?, lesson_time=?, lesson_type=?, subject=?, teacher=?, room=? WHERE id=?',
                 (faculty, course, group, day, lesson_time, lesson_type, subject, teacher, room, id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Jadval muvaffaqiyatli yangilandi!'})

if __name__ == '__main__':
    migrate_to_sqlite()
    init_users_db()  # Foydalanuvchilar bazasini ishga tushirish
    app.run(debug=True, host='0.0.0.0', port=5000)