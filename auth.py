import sqlite3
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = 'users.db'

def init_users_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Jadvalni yaratishda is_admin ustunini qo‘shamiz
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  is_admin INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        if c.fetchone():
            flash('Bu email allaqachon ro‘yxatdan o‘tgan! Boshqa email kiriting.', 'danger')
            conn.close()
            return render_template('register.html')
        
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if c.fetchone():
            flash('Bu foydalanuvchi nomi allaqachon band! Boshqa nom tanlang.', 'danger')
            conn.close()
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        c.execute("INSERT INTO users (name, email, username, password, is_admin) VALUES (?, ?, ?, ?, ?)",
                  (name, email, username, hashed_password, 0))
        conn.commit()
        conn.close()
        
        session['username'] = username
        session['is_admin'] = 0
        flash('Ro‘yxatdan o‘tish muvaffaqiyatli amalga oshirildi! Tizimga xush kelibsiz.', 'success')
        return redirect(url_for('main'))
    
    return render_template('register.html')

def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user:
            if check_password_hash(user[4], password):
                session['username'] = username
                session['is_admin'] = user[5]  # is_admin ustuni endi mavjud bo‘ladi
                flash('Tizimga muvaffaqiyatli kirdingiz! Xush kelibsiz.', 'success')
                return redirect(url_for('main'))
            else:
                flash('Parol noto‘g‘ri! Iltimos, qayta urinib ko‘ring.', 'danger')
        else:
            flash('Bunday foydalanuvchi mavjud emas! Iltimos, ro‘yxatdan o‘ting.', 'danger')
    
    return render_template('login.html')