from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User
from config import Config
from routes.admin import admin
from routes.teacher import teacher
from routes.student import student

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()

app.register_blueprint(admin)
app.register_blueprint(teacher)
app.register_blueprint(student)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Проверяем существование админа
    if not User.is_admin_exists() and request.method == 'POST':
        # Создаем первого админа
        admin = User(
            username=request.form.get('username'),
            email=request.form.get('username') + '@admin.com',
            role='admin',
            full_name='System Administrator'
        )
        admin.set_password(request.form.get('password'))
        db.session.add(admin)
        db.session.commit()
        login_user(admin)
        flash('Admin account created successfully!')
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            # Редирект в зависимости от роли
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        
        flash('Invalid username or password')
    return render_template('login.html', is_first_login=not User.is_admin_exists())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
