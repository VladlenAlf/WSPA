from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Course, SystemLog, CourseEnrollment, Assignment, Submission, Message

admin = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    users = User.query.all()
    total_users = len(users)
    total_courses = Course.query.count()
    return render_template('admin/dashboard.html', 
                         users=users,
                         total_users=total_users,
                         total_courses=total_courses)

@admin.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        # Check if user with this email or username already exists
        if User.query.filter_by(email=request.form['email']).first():
            flash('Email already registered!', 'error')
            return render_template('admin/create_user.html')
            
        if User.query.filter_by(username=request.form['username']).first():
            flash('Username already taken!', 'error')
            return render_template('admin/create_user.html')
            
        try:
            user = User(
                username=request.form['username'],
                email=request.form['email'],
                full_name=request.form['full_name'],
                role=request.form['role']
            )
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.commit()
            log_admin_action(f"Created new user: {user.username}")
            flash('User created successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
            return render_template('admin/create_user.html')
            
    return render_template('admin/create_user.html')

@admin.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.full_name = request.form['full_name']
        user.role = request.form['role']
        
        if request.form.get('password'):
            user.set_password(request.form['password'])
        
        db.session.commit()
        log_admin_action(f"Updated user: {user.username}")
        flash('User updated successfully!')
        return redirect(url_for('admin.dashboard'))
        
    return render_template('admin/edit_user.html', user=user)

@admin.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting self or other admins
    if user.id == current_user.id or user.role == 'admin':
        flash('Cannot delete admin users!', 'error')
        return redirect(url_for('admin.dashboard'))
    
    try:
        # Если это учитель, проверяем и удаляем связанные курсы
        if user.role == 'teacher':
            courses = Course.query.filter_by(teacher_id=user.id).all()
            for course in courses:
                # Удаляем все записи о регистрации на курс
                CourseEnrollment.query.filter_by(course_id=course.id).delete()
                # Получаем все задания курса
                assignments = Assignment.query.filter_by(course_id=course.id).all()
                for assignment in assignments:
                    # Удаляем все решения для каждого задания
                    Submission.query.filter_by(assignment_id=assignment.id).delete()
                    db.session.delete(assignment)
                db.session.delete(course)
        
        # Если это студент, удаляем его регистрации и решения
        if user.role == 'student':
            # Удаляем все регистрации на курсы
            CourseEnrollment.query.filter_by(student_id=user.id).delete()
            # Удаляем все решения заданий
            Submission.query.filter_by(student_id=user.id).delete()
        
        # Удаляем все сообщения пользователя
        Message.query.filter((Message.sender_id == user.id) | 
                           (Message.receiver_id == user.id)).delete()
        
        # Наконец, удаляем самого пользователя
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {user.username} and all related data deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/admin/courses')
@login_required
@admin_required
def manage_courses():
    courses = Course.query.all()
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/courses.html', courses=courses, teachers=teachers)

@admin.route('/admin/course/<int:course_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course(course_id):
    try:
        course = Course.query.get_or_404(course_id)
        course_name = course.name
        db.session.delete(course)
        db.session.commit()
        log_admin_action(f"Deleted course: {course_name}")
        flash('Course deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting course: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_courses'))

@admin.route('/admin/course/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_course():
    if request.method == 'POST':
        try:
            course = Course(
                name=request.form['name'],
                description=request.form['description'],
                teacher_id=request.form['teacher_id']
            )
            db.session.add(course)
            db.session.commit()
            log_admin_action(f"Created new course: {course.name}")
            flash('Course created successfully!', 'success')
            return redirect(url_for('admin.manage_courses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating course: {str(e)}', 'error')
            return render_template('admin/create_course.html', teachers=User.query.filter_by(role='teacher').all())
            
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/create_course.html', teachers=teachers)

@admin.route('/admin/course/<int:course_id>/enrollments', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_enrollments(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        action = request.form.get('action')
        
        try:
            if action == 'enroll':
                enrollment = CourseEnrollment(course_id=course_id, student_id=student_id)
                db.session.add(enrollment)
                log_admin_action(f"Enrolled student {student_id} in course {course.name}")
                flash('Student enrolled successfully!', 'success')
            elif action == 'unenroll':
                enrollment = CourseEnrollment.query.filter_by(
                    course_id=course_id, 
                    student_id=student_id
                ).first()
                if enrollment:
                    db.session.delete(enrollment)
                    log_admin_action(f"Unenrolled student {student_id} from course {course.name}")
                    flash('Student unenrolled successfully!', 'success')
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error managing enrollment: {str(e)}', 'error')
    
    enrolled_students = User.query.join(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id
    ).all()
    available_students = User.query.filter(
        User.role == 'student',
        ~User.id.in_([s.id for s in enrolled_students])
    ).all()
    
    return render_template('admin/manage_enrollments.html',
                         course=course,
                         enrolled_students=enrolled_students,
                         available_students=available_students)

@admin.route('/admin/logs')
@login_required
@admin_required
def view_logs():
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(100).all()
    return render_template('admin/logs.html', logs=logs, User=User)

@admin.route('/admin/analytics')
@login_required
@admin_required
def analytics():
    # Gather analytics data
    analytics_data = {
        'total_users': User.query.count(),
        'total_students': User.query.filter_by(role='student').count(),
        'total_teachers': User.query.filter_by(role='teacher').count(),
        'total_courses': Course.query.count(),
        'recent_activities': SystemLog.query.order_by(SystemLog.created_at.desc()).limit(5).all(),
        'course_distribution': db.session.query(
            Course.name,
            db.func.count(CourseEnrollment.id).label('student_count')
        ).outerjoin(CourseEnrollment).group_by(Course.id).all()
    }
    
    return render_template('admin/analytics.html', data=analytics_data)

def log_admin_action(action):
    log = SystemLog(
        user_id=current_user.id,
        action=action,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
