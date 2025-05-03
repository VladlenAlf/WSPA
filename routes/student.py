from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from functools import wraps
from models import db, Course, CourseEnrollment, Assignment, Submission, Material, User, Message
from datetime import datetime
import os
from werkzeug.utils import secure_filename

student = Blueprint('student', __name__)

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('Access denied.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@student.route('/student/dashboard')
@login_required
@student_required
def dashboard():
    enrollments = CourseEnrollment.query.filter_by(student_id=current_user.id).all()
    my_courses = [Course.query.get(e.course_id) for e in enrollments]
    
    # Получаем активные задания
    active_assignments = []
    for course in my_courses:
        assignments = Assignment.query.filter_by(course_id=course.id).all()
        for assignment in assignments:
            if assignment.due_date > datetime.utcnow():
                active_assignments.append(assignment)
    
    return render_template('student/dashboard.html', 
                         courses=my_courses, 
                         assignments=active_assignments)

@student.route('/student/courses')
@login_required
@student_required
def available_courses():
    enrolled_courses = CourseEnrollment.query.filter_by(student_id=current_user.id).all()
    enrolled_ids = [e.course_id for e in enrolled_courses]
    available_courses = Course.query.filter(~Course.id.in_(enrolled_ids)).all()
    return render_template('student/available_courses.html', courses=available_courses)

@student.route('/student/enroll/<int:course_id>')
@login_required
@student_required
def enroll_course(course_id):
    enrollment = CourseEnrollment(course_id=course_id, student_id=current_user.id)
    db.session.add(enrollment)
    db.session.commit()
    flash('Successfully enrolled in the course!')
    return redirect(url_for('student.dashboard'))

@student.route('/student/submit-assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
@student_required
def submit_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Проверяем, не истек ли срок сдачи
    if assignment.due_date < datetime.utcnow():
        flash('Assignment submission deadline has passed!')
        return redirect(url_for('student.dashboard'))
        
    if request.method == 'POST':
        try:
            content = request.form.get('content')
            file = request.files.get('submission_file')
            file_path = None
            
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Create submissions directory
                submissions_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'submissions')
                os.makedirs(submissions_dir, exist_ok=True)
                # Save with unique filename
                file_path = os.path.join('submissions', f"{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], file_path))

            submission = Submission(
                assignment_id=assignment_id,
                student_id=current_user.id,
                content=content,
                file_path=file_path
            )
            
            db.session.add(submission)
            db.session.commit()
            flash('Assignment submitted successfully!', 'success')
            return redirect(url_for('student.view_assignment', assignment_id=assignment_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting assignment: {str(e)}', 'error')
    
    return render_template('student/submit_assignment.html', assignment=assignment)

@student.route('/submission/download/<int:submission_id>')
@login_required
def download_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if current_user.id != submission.student_id and \
       current_user.role != 'teacher' and \
       current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
        
    if submission.file_path:
        try:
            return send_from_directory(
                current_app.config['UPLOAD_FOLDER'],
                submission.file_path,
                as_attachment=True
            )
        except Exception as e:
            flash(f'Error downloading file: {str(e)}', 'error')
    
    return redirect(url_for('student.view_assignment', assignment_id=submission.assignment_id))

@student.route('/student/submissions')
@login_required
@student_required
def my_submissions():
    submissions = Submission.query.filter_by(student_id=current_user.id).all()
    return render_template('student/submissions.html', submissions=submissions)

@student.route('/student/grades')
@login_required
@student_required
def view_grades():
    submissions = Submission.query.filter_by(student_id=current_user.id).all()
    return render_template('student/grades.html', submissions=submissions)

@student.route('/student/course/<int:course_id>/materials')
@login_required
@student_required
def course_materials(course_id):
    # Проверяем, записан ли студент на курс
    enrollment = CourseEnrollment.query.filter_by(
        course_id=course_id, 
        student_id=current_user.id
    ).first()
    
    if not enrollment:
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student.dashboard'))
    
    course = Course.query.get_or_404(course_id)
    assignments = Assignment.query.filter_by(course_id=course_id).order_by(Assignment.due_date.desc()).all()
    
    # Получаем статус заданий (сдано/не сдано)
    submissions = {s.assignment_id: s for s in Submission.query.filter_by(student_id=current_user.id).all()}
    
    return render_template('student/course_materials.html', 
                         course=course,
                         assignments=assignments,
                         submissions=submissions)

@student.route('/student/material/<int:material_id>/download')
@login_required
@student_required
def download_material(material_id):
    material = Material.query.get_or_404(material_id)
    
    # Проверяем доступ к материалу
    enrollment = CourseEnrollment.query.filter_by(
        course_id=material.course_id, 
        student_id=current_user.id
    ).first()
    
    if not enrollment:
        flash('Access denied.')
        return redirect(url_for('student.dashboard'))
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        material.file_path,
        as_attachment=True
    )

@student.route('/student/messages')
@login_required
@student_required
def messages():
    # Получаем всех учителей из курсов студента
    course_teachers = db.session.query(User).join(Course, Course.teacher_id == User.id)\
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)\
        .filter(CourseEnrollment.student_id == current_user.id).distinct().all()
    
    # Получаем все сообщения
    messages = Message.query.filter_by(receiver_id=current_user.id).all()
    
    return render_template('student/messages.html', 
                         teachers=course_teachers,
                         messages=messages)

@student.route('/student/chat/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
@student_required
def chat_with_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    
    # Отмечаем сообщения как прочитанные при входе в чат
    Message.query.filter_by(
        sender_id=teacher_id,
        receiver_id=current_user.id,
        read=False
    ).update({Message.read: True})
    
    if request.method == 'POST':
        content = request.form.get('message')
        if content:
            message = Message(
                sender_id=current_user.id,
                receiver_id=teacher_id,
                content=content
            )
            db.session.add(message)
    
    db.session.commit()  # Сохраняем изменения статуса прочтения и новые сообщения
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == teacher_id)) |
        ((Message.sender_id == teacher_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at).all()
    
    return render_template('student/chat.html', 
                         other_user=teacher, 
                         messages=messages)

@student.route('/student/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
@student_required
def chat(user_id):
    other_user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        content = request.form.get('content')
        message = Message(
            sender_id=current_user.id,
            receiver_id=user_id,
            content=content
        )
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('student.chat', user_id=user_id))
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    # Отмечаем сообщения как прочитанные
    unread_messages = Message.query.filter_by(
        receiver_id=current_user.id,
        sender_id=user_id,
        read=False
    ).all()
    
    for message in unread_messages:
        message.read = True
    db.session.commit()
    
    return render_template('student/chat.html', 
                         other_user=other_user, 
                         messages=messages)

@student.route('/student/assignment/<int:assignment_id>/view')
@login_required
@student_required
def view_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    # Check if student is enrolled in the course
    enrollment = CourseEnrollment.query.filter_by(
        course_id=assignment.course_id,
        student_id=current_user.id
    ).first()
    
    if not enrollment:
        flash('You are not enrolled in this course', 'error')
        return redirect(url_for('student.dashboard'))
        
    # Get student's submission if exists
    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).first()
    
    return render_template('student/view_assignment.html', 
                         assignment=assignment,
                         submission=submission)

@student.route('/student/assignment/download/<int:assignment_id>')
@login_required
@student_required
def download_assignment_file(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    # Check if student is enrolled
    enrollment = CourseEnrollment.query.filter_by(
        course_id=assignment.course_id,
        student_id=current_user.id
    ).first()
    
    if not enrollment:
        flash('Access denied', 'error')
        return redirect(url_for('student.dashboard'))
        
    if not assignment.file_path:
        flash('No file attached to this assignment', 'error')
        return redirect(url_for('student.view_assignment', assignment_id=assignment_id))

    try:
        # Handle Windows paths by splitting and taking the last part
        filename = os.path.basename(assignment.file_path)
        directory = os.path.dirname(os.path.join(current_app.config['UPLOAD_FOLDER'], assignment.file_path))
        
        if not os.path.exists(os.path.join(directory, filename)):
            flash('File not found', 'error')
            return redirect(url_for('student.view_assignment', assignment_id=assignment_id))
            
        return send_from_directory(
            directory,
            filename,
            as_attachment=True
        )
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('student.view_assignment', assignment_id=assignment_id))

@student.route('/student/profile', methods=['GET', 'POST'])
@login_required
@student_required
def profile():
    if request.method == 'POST':
        try:
            current_user.full_name = request.form['full_name']
            current_user.email = request.form['email']
            
            if request.form.get('new_password'):
                if current_user.check_password(request.form['current_password']):
                    current_user.set_password(request.form['new_password'])
                else:
                    flash('Current password is incorrect', 'error')
                    return redirect(url_for('student.profile'))
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('student.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    return render_template('student/profile.html')
