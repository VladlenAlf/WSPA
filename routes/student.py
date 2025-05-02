from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
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
        content = request.form.get('content')
        file = request.files.get('submission_file')
        
        submission = Submission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            content=content
        )
        
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            submission.file_path = filename
            
        db.session.add(submission)
        db.session.commit()
        flash('Assignment submitted successfully!')
        return redirect(url_for('student.dashboard'))
        
    return render_template('student/submit_assignment.html', assignment=assignment)

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
        flash('You are not enrolled in this course.')
        return redirect(url_for('student.dashboard'))
    
    course = Course.query.get_or_404(course_id)
    materials = Material.query.filter_by(course_id=course_id).order_by(Material.uploaded_at.desc()).all()
    return render_template('student/course_materials.html', course=course, materials=materials)

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
    chats = db.session.query(User).join(Message, 
        (Message.sender_id == User.id) | (Message.receiver_id == User.id)
    ).filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).distinct().all()
    
    return render_template('student/messages.html', chats=chats)

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
