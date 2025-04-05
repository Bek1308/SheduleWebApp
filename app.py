from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime, timedelta
from auth import init_users_db, register, login  # auth.py dan import
import hashlib
from difflib import SequenceMatcher

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

def generate_teacher_code(teacher_name, teacher_id):
    hash_input = f"{teacher_name}{teacher_id}".encode('utf-8')
    hash_output = hashlib.md5(hash_input).hexdigest()[:6]
    return hash_output.upper()

def migrate_schedules():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Eski jadvalni o'chirish (agar mavjud bo'lsa)
    cursor.execute("DROP TABLE IF EXISTS schedules")

    # Schedules jadvalini qayta yaratish
    cursor.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty TEXT NOT NULL,
        course TEXT NOT NULL,
        "group" TEXT NOT NULL,
        day TEXT NOT NULL,
        lesson_time TEXT NOT NULL,
        lesson_type TEXT,
        subject TEXT NOT NULL,
        teacher TEXT NOT NULL,
        room TEXT NOT NULL,
        week_type TEXT NOT NULL CHECK (week_type IN ('Четный', 'Нечетный'))
    )''')

    # Schedules jadvalini .txt fayllardan to‘ldirish
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
                    
                    seen_times_by_day = {}
                    for day, data in schedule.items():
                        day_key = day.split()[0]
                        if day_key not in seen_times_by_day:
                            seen_times_by_day[day_key] = {}
                        for lesson in data['lessons']:
                            time_key = lesson['time']
                            if time_key not in seen_times_by_day[day_key]:
                                seen_times_by_day[day_key][time_key] = []
                            seen_times_by_day[day_key][time_key].append(lesson)
                    
                    for day, data in schedule.items():
                        day_key = day.split()[0]
                        for time_key, lessons in seen_times_by_day[day_key].items():
                            if len(lessons) == 1:
                                lesson = lessons[0]
                                for week_type in ["Четный", "Нечетный"]:
                                    cursor.execute('''INSERT INTO schedules 
                                        (faculty, course, "group", day, lesson_time, lesson_type, subject, teacher, room, week_type)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                        (faculty, course, group, day_key, lesson['time'], 
                                         lesson['type'] or '', lesson['subject'] or '', lesson['teacher'] or '', 
                                         lesson['room'] or '', week_type))
                            else:
                                for i, lesson in enumerate(lessons):
                                    week_type = "Четный" if i == 0 else "Нечетный"
                                    cursor.execute('''INSERT INTO schedules 
                                        (faculty, course, "group", day, lesson_time, lesson_type, subject, teacher, room, week_type)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                        (faculty, course, group, day_key, lesson['time'], 
                                         lesson['type'] or '', lesson['subject'] or '', lesson['teacher'] or '', 
                                         lesson['room'] or '', week_type))

    conn.commit()
    conn.close()
    print("✅ Schedules jadvali migratsiyasi muvaffaqiyatli yakunlandi.")

DAYS_OF_WEEK = ["Душанбе", "Сешанбе", "Чоршанбе", "Панҷшанбе", "Ҷумъа", "Шанбе", "Якшанбе"]

def normalize_day_name(day_name):
    return day_name.strip().lower().replace(" ", "")

def find_closest_day(day_from_file, threshold=0.8):
    normalized_input = normalize_day_name(day_from_file)
    best_match = None
    highest_similarity = 0
    for day in DAYS_OF_WEEK:
        normalized_day = normalize_day_name(day)
        similarity = SequenceMatcher(None, normalized_input, normalized_day).ratio()
        if similarity > highest_similarity and similarity >= threshold:
            highest_similarity = similarity
            best_match = day
    return best_match

def normalize_teacher_name(teacher_name):
    teacher_name = teacher_name.strip()
    prefixes = ["н.и техникӣ", "н.и.иқтисодӣ", "н.и.", "дотс.", "проф.", "техникӣ", "иқтисодӣ", "доц.", "профессор", "профессори", "доцент", "доценти","таърих", "таърихи", "мудири"]
    for prefix in prefixes:
        if prefix in teacher_name:
            teacher_name = teacher_name.replace(prefix, "").strip()
    parts = teacher_name.split()
    if len(parts) == 1:
        return parts[0]
    elif len(parts) > 1 and parts[-1].replace(".", "").isupper():
        return " ".join(parts[-2:])
    return teacher_name

def are_names_similar(name1, name2, threshold=0.8):
    similarity = SequenceMatcher(None, name1, name2).ratio()
    return similarity >= threshold

def find_existing_teacher(cursor, teacher_name, existing_teachers):
    normalized_new = normalize_teacher_name(teacher_name)
    for existing in existing_teachers:
        normalized_existing = normalize_teacher_name(existing)
        if are_names_similar(normalized_new, normalized_existing):
            return existing
    return None

def migrate_teachers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_name TEXT NOT NULL UNIQUE,
        teacher_code TEXT NOT NULL
    )''')
    cursor.execute('SELECT DISTINCT teacher FROM schedules WHERE teacher IS NOT NULL AND teacher != ""')
    raw_teachers = [row['teacher'] for row in cursor.fetchall()]
    cursor.execute('SELECT teacher_name FROM teachers')
    existing_teachers = [row['teacher_name'] for row in cursor.fetchall()]
    for teacher in raw_teachers:
        matched_teacher = find_existing_teacher(cursor, teacher, existing_teachers)
        if matched_teacher:
            print(f"ℹ️ Muallim '{teacher}' '{matched_teacher}' bilan birlashtirildi.")
            continue
        normalized_name = normalize_teacher_name(teacher)
        try:
            cursor.execute('INSERT INTO teachers (teacher_name, teacher_code) VALUES (?, ?)', 
                          (normalized_name, 'temp_code'))
            teacher_id = cursor.lastrowid
            teacher_code = generate_teacher_code(normalized_name, teacher_id)
            cursor.execute('UPDATE teachers SET teacher_code=? WHERE id=?', (teacher_code, teacher_id))
            existing_teachers.append(normalized_name)
            print(f"✅ Muallim '{normalized_name}' qo‘shildi, ID: {teacher_id}, Kod: {teacher_code}")
        except Exception as e:
            print(f"❌ Muallim '{normalized_name}' qo‘shishda xato: {e}")
    conn.commit()
    conn.close()
    print("✅ Teachers jadvali migratsiyasi muvaffaqiyatli yakunlandi.")

def get_current_week_dates():
    today = datetime.now()
    week_dates = {}
    for i in range(7):
        target_date = today + timedelta(days=i)
        weekday_num = target_date.weekday()
        day_name = DAYS_OF_WEEK[weekday_num]
        week_dates[day_name] = target_date.strftime("%d.%m.%Y")
    return week_dates

def get_week_type():
    today = datetime.today()
    week_number = today.isocalendar()[1]
    return 'Четный' if week_number % 2 == 0 else 'Нечетный'

def display_week_type(week_type):
    """Ma'lumotlar bazasidagi hafta turini UI uchun o'zgartirish."""
    return "Сурат" if week_type == "Четный" else "Махрач"

def parse_schedule(content):
    schedule = {}
    current_day = None
    file_schedule = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        potential_day = find_closest_day(line)
        if potential_day:
            current_day = potential_day
            file_schedule[current_day] = []
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
        return redirect(url_for('main'))
    return render_template('index1.html')

@app.route('/main')
def main():
    if 'username' not in session:
        flash('Sizda tizimga kirishga ruxsat yo‘q! Iltimos, avval tizimga kiring.', 'danger')
        return redirect(url_for('login'))
    return render_template('main.html', username=session['username'], is_admin=session.get('is_admin', 0))

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    return login()

@app.route('/register', methods=['GET', 'POST'])
def register_route():
    return register()

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
    day = request.args.get('day')
    conn = get_db_connection()
    lessons = conn.execute('SELECT * FROM schedules WHERE faculty=? AND course=? AND "group"=?',
                          (faculty, course, group)).fetchall()
    conn.close()

    current_week_type = get_week_type()
    week_types = ['Четный', 'Нечетный'] if current_week_type == 'Четный' else ['Нечетный', 'Четный']
    display_week_types = {week_type: display_week_type(week_type) for week_type in week_types}
    
    schedule = {week_type: {} for week_type in week_types}
    week_dates = get_current_week_dates()
    ordered_days = DAYS_OF_WEEK
    
    today = datetime.today().strftime('%d.%m.%Y')
    current_day = DAYS_OF_WEEK[datetime.today().weekday()]
    
    for week_type in week_types:
        for day_name in ordered_days:
            schedule[week_type][day_name] = {
                'date': week_dates[day_name],
                'weekday': DAYS_OF_WEEK.index(day_name),
                'lessons': [],
                'is_today': day_name == current_day and week_dates[day_name] == today and week_type == current_week_type
            }
    
    for lesson in lessons:
        day_name = lesson['day']
        week_type = lesson['week_type']
        if day_name in schedule[week_type]:
            schedule[week_type][day_name]['lessons'].append({
                'time': lesson['lesson_time'],
                'type': lesson['lesson_type'],
                'subject': lesson['subject'],
                'teacher': lesson['teacher'],
                'room': lesson['room']
            })

    return render_template('schedule.html', schedule=schedule, group=f"{faculty} | {course} | {group}-гуруҳ", 
                          day=day, display_week_types=display_week_types)

@app.route('/get_day/<faculty>/<course>/<group>')
def get_day_schedule(faculty, course, group):
    day = request.args.get('day')
    current_week_type = get_week_type()
    display_current_week_type = display_week_type(current_week_type)
    conn = get_db_connection()
    lessons = conn.execute('SELECT * FROM schedules WHERE faculty=? AND course=? AND "group"=? AND LOWER(day)=LOWER(?) AND week_type=?',
                          (faculty, course, group, day, current_week_type)).fetchall()
    conn.close()
    
    if not lessons and day != "Якшанбе":
        return f"❌ Дар ин рӯз ({day}) барои гуруҳи--{group} жадвали дарси вуҷуд надорад (Хафтаи {display_current_week_type})!"
    elif day == "Якшанбе":
        return f"📅 {day} - {faculty} | {course} | {group}-гуруҳ\n\n❌ Дар ин рӯз жадвали дарси вуҷуд надорад!"
    
    response = f"📅 {day} - {faculty} | {course} | {group}-гуруҳ (Хафтаи {display_current_week_type})\n\n"
    for lesson in lessons:
        response += f"⏰ {lesson['lesson_time']}\n🔖 {lesson['lesson_type']}\n📌 {lesson['subject']}\n👨‍🏫 {lesson['teacher']}\n🏫 {lesson['room']}\n\n"
    return response

@app.route('/teacher/<teacher_code>')
def show_teacher_schedule(teacher_code): 
    conn = get_db_connection()
    try:
        teacher = conn.execute('SELECT teacher_name FROM teachers WHERE teacher_code=?', (teacher_code,)).fetchone()
        if not teacher:
            flash('Noto‘g‘ri muallim kodi!', 'danger')
            return redirect(url_for('main'))
        
        teacher_name = teacher['teacher_name']
        
        lessons = conn.execute('SELECT * FROM schedules ORDER BY lesson_time').fetchall()
        
        current_week_type = get_week_type()
        week_types = ['Четный', 'Нечетный'] if current_week_type == 'Четный' else ['Нечетный', 'Четный']
        display_week_types = {week_type: display_week_type(week_type) for week_type in week_types}
        
        schedule = {week_type: {} for week_type in week_types}
        week_dates = get_current_week_dates()
        ordered_days = DAYS_OF_WEEK
        
        today = datetime.today().strftime('%d.%m.%Y')
        current_day = DAYS_OF_WEEK[datetime.today().weekday()]
        
        for week_type in week_types:
            for day_name in ordered_days:
                schedule[week_type][day_name] = {
                    'date': week_dates[day_name],
                    'weekday': DAYS_OF_WEEK.index(day_name),
                    'lessons': [],
                    'is_today': day_name == current_day and week_dates[day_name] == today and week_type == current_week_type
                }
        
        for lesson in lessons:
            lesson_teacher = lesson['teacher']
            normalized_lesson_teacher = normalize_teacher_name(lesson_teacher)
            if are_names_similar(normalized_lesson_teacher, teacher_name, threshold=0.85):
                day_name = lesson['day']
                week_type = lesson['week_type']
                if day_name in schedule[week_type]:
                    schedule[week_type][day_name]['lessons'].append({
                        'time': lesson['lesson_time'],
                        'type': lesson['lesson_type'],
                        'subject': lesson['subject'],
                        'room': lesson['room'],
                        'group': f"{lesson['faculty']} | {lesson['course']} | {lesson['group']}"
                    })
        
        for week_type in week_types:
            for day_name in ordered_days:
                lessons = schedule[week_type][day_name]['lessons']
                if lessons:
                    lessons_by_time = {}
                    for lesson in lessons:
                        time = lesson['time']
                        if time not in lessons_by_time:
                            lessons_by_time[time] = []
                        lessons_by_time[time].append(lesson)
                    
                    new_lessons = []
                    for time in sorted(lessons_by_time.keys()):
                        time_lessons = lessons_by_time[time]
                        groups = [l['group'] for l in time_lessons]
                        first_lesson = time_lessons[0]
                        new_lessons.append({
                            'time': time,
                            'type': first_lesson['type'],
                            'subject': first_lesson['subject'],
                            'room': first_lesson['room'],
                            'groups': groups
                        })
                    schedule[week_type][day_name]['lessons'] = new_lessons
        
    finally:
        conn.close()

    return render_template('teacher_schedule.html', schedule=schedule, teacher_name=teacher_name, 
                          teacher_code=teacher_code, display_week_types=display_week_types)

@app.route('/get_teacher_day/<teacher_code>')
def get_teacher_day_schedule(teacher_code):
    day = request.args.get('day')
    current_week_type = get_week_type()
    display_current_week_type = display_week_type(current_week_type)
    conn = get_db_connection()
    try:
        teacher = conn.execute('SELECT teacher_name FROM teachers WHERE teacher_code=?', (teacher_code,)).fetchone()
        if not teacher:
            return "❌ Noto‘g‘ri kod!"
        
        teacher_name = teacher['teacher_name']
        
        lessons = conn.execute('''
            SELECT * FROM schedules 
            WHERE LOWER(day)=LOWER(?) AND week_type=? 
            ORDER BY lesson_time
        ''', (day, current_week_type)).fetchall()
        
        filtered_lessons = []
        for lesson in lessons:
            lesson_teacher = lesson['teacher']
            normalized_lesson_teacher = normalize_teacher_name(lesson_teacher)
            if are_names_similar(normalized_lesson_teacher, teacher_name, threshold=0.85):
                filtered_lessons.append(dict(lesson))
        
        if not filtered_lessons and day != "Якшанбе":
            return f"❌ Дар ин рӯз ({day}) устод {teacher_name} барои шумо жадвали дарсӣ вуҷуд надорад ({display_current_week_type} ҳафта)!"
        elif day == "Якшанбе":
            return f"📅 {day} - Устод: {teacher_name}\n\n❌ Дар ин рӯз жадвали дарсӣ вуҷуд надорад!"
        
        lessons_by_time = {}
        for lesson in filtered_lessons:
            time = lesson['lesson_time']
            if time not in lessons_by_time:
                lessons_by_time[time] = []
            lessons_by_time[time].append(lesson)
        
        response = f"<b>📅 {day} - Устод: {teacher_name} (Хафтаи {display_current_week_type})</b>\n\n"
        for time in sorted(lessons_by_time.keys()):
            lessons = lessons_by_time[time]
            groups = [f"{l['faculty']} | {l['course']} | {l['group']}" for l in lessons]
            first_lesson = lessons[0]
            groups_html = "\n".join([f"    ➡️ {group}" for group in groups])
            response += (
                f"<b>⏰ {time}</b>\n"
                f"🔖 {first_lesson['lesson_type']}\n"
                f"📌 {first_lesson['subject']}\n"
                f"🏫 {first_lesson['room']}\n"
                f"👥 <b>Гурӯҳ(лар):</b>\n{groups_html}\n\n"
            )
        return response
    finally:
        conn.close()

@app.route('/get_teachers_with_codes')
def get_teachers_with_codes():
    conn = get_db_connection()
    try:
        teachers = conn.execute('SELECT teacher_name, teacher_code FROM teachers').fetchall()
        result = [{"teacher_name": t['teacher_name'], "teacher_code": t['teacher_code']} for t in teachers]
    finally:
        conn.close()
    return jsonify(result)

@app.route('/check_teacher_code', methods=['POST'])
def check_teacher_code():
    data = request.json
    teacher_code = data.get('teacher_code')
    conn = get_db_connection()
    try:
        teacher = conn.execute('SELECT teacher_name FROM teachers WHERE teacher_code=?', (teacher_code,)).fetchone()
        if teacher:
            return jsonify({"status": "success", "teacher_name": teacher['teacher_name']})
        return jsonify({"status": "error", "message": "Noto‘g‘ri kod!"})
    finally:
        conn.close()

@app.route('/pages/<page_name>')
def load_page(page_name):
    try:
        return render_template(f'{page_name}.html')
    except:
        return "<h1>Xato</h1><p>Sahifa topilmadi!</p>", 404

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'username' not in session:
        flash('Sizda admin paneliga kirishga ruxsat yo‘q! Iltimos, tizimga kiring.', 'danger')
        return redirect(url_for('login'))
    
    if not session.get('is_admin', 0):
        flash('Sizda admin huquqlari yo‘q! Faqat administratorlar bu sahifaga kirishi mumkin.', 'danger')
        return redirect(url_for('main'))
    
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
    ordered_days = list(week_dates.keys())

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
                          days=ordered_days,
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
    week_type = request.form.get('week_type', 'Четный')  # Ma'lumotlar bazasida "Четный" saqlanadi
    
    conn.execute('INSERT INTO schedules (faculty, course, "group", day, lesson_time, lesson_type, subject, teacher, room, week_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (faculty, course, group, day, lesson_time, lesson_type, subject, teacher, room, week_type))
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
    week_type = request.form.get('week_type', 'Четный')  # Ma'lumotlar bazasida "Четный" saqlanadi
    
    conn.execute('UPDATE schedules SET faculty=?, course=?, "group"=?, day=?, lesson_time=?, lesson_type=?, subject=?, teacher=?, room=?, week_type=? WHERE id=?',
                 (faculty, course, group, day, lesson_time, lesson_type, subject, teacher, room, week_type, id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Jadval muvaffaqiyatli yangilandi!'})

if __name__ == '__main__':
    migrate_schedules()
    migrate_teachers()
    init_users_db()
    app.run(debug=True, host='0.0.0.0', port=5000)