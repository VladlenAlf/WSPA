from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from functools import wraps
from models import db, Course, Assignment, Submission, Material, User, Message, CourseEnrollment
from datetime import datetime
from werkzeug.utils import secure_filename
import os

teacher = Blueprint('teacher', __name__)

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('Access denied.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@teacher.route('/teacher/dashboard')
@login_required
@teacher_required
def dashboard():
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    recent_submissions = Submission.query.join(Assignment).join(Course).filter(
        Course.teacher_id == current_user.id,
        Submission.grade == None
    ).order_by(Submission.submitted_at.desc()).limit(5).all()
    return render_template('teacher/dashboard.html', 
                         courses=courses,
                         recent_submissions=recent_submissions)

@teacher.route('/teacher/course/<int:course_id>')
@login_required
@teacher_required
def course_details(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('teacher.dashboard'))
    return render_template('teacher/course_details.html', course=course)

@teacher.route('/teacher/course/<int:course_id>/assignments', methods=['GET', 'POST'])
@login_required
@teacher_required
def manage_assignments(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        try:
            file = request.files.get('assignment_file')
            file_path = None
            
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Ensure assignments directory exists
                assignments_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'assignments')
                os.makedirs(assignments_dir, exist_ok=True)
                # Save file with unique filename
                file_path = os.path.join('assignments', f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], file_path))

            assignment = Assignment(
                course_id=course_id,
                title=request.form['title'],
                description=request.form['description'],
                file_path=file_path,
                due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%dT%H:%M')
            )
            db.session.add(assignment)
            db.session.commit()
            flash('Assignment created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating assignment: {str(e)}', 'error')

    assignments = Assignment.query.filter_by(course_id=course_id).all()
    return render_template('teacher/assignments.html', 
                         course=course,
                         assignments=assignments)

@teacher.route('/teacher/grade/<int:submission_id>', methods=['POST'])
@login_required
@teacher_required
def grade_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    course = Course.query.get(submission.assignment.course_id)
    
    if course.teacher_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('teacher.dashboard'))
    
    grade = request.form.get('grade')
    feedback = request.form.get('feedback')
    
    submission.grade = grade
    submission.feedback = feedback
    db.session.commit()
    
    flash('Submission graded successfully!')
    return redirect(url_for('teacher.view_submissions', 
                          assignment_id=submission.assignment_id))

@teacher.route('/teacher/assignment/<int:assignment_id>/submissions')
@login_required
@teacher_required
def view_submissions(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.course.teacher_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('teacher.dashboard'))
    
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    return render_template('teacher/view_submissions.html', 
                         assignment=assignment,
                         submissions=submissions)

@teacher.route('/api/submission/<int:submission_id>')
@login_required
@teacher_required
def get_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.assignment.course.teacher_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'content': submission.content,
        'file_path': submission.file_path
    })

@teacher.route('/teacher/course/<int:course_id>/assignment/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_assignment(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        try:
            # Handle file upload
            file = request.files.get('assignment_file')
            file_path = None
            
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Create assignments directory if it doesn't exist
                assignments_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'assignments')
                os.makedirs(assignments_dir, exist_ok=True)
                file_path = os.path.join('assignments', filename)
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], file_path))

            assignment = Assignment(
                course_id=course_id,
                title=request.form['title'],
                description=request.form['description'],
                file_path=file_path,
                due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%dT%H:%M')
            )
            
            db.session.add(assignment)
            db.session.commit()
            flash('Assignment created successfully!', 'success')
            return redirect(url_for('teacher.manage_assignments', course_id=course_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating assignment: {str(e)}', 'error')
            
    return render_template('teacher/create_assignment.html', course=course)

@teacher.route('/download/assignment/<int:assignment_id>')
@login_required
def download_assignment_file(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if not assignment.file_path:
        flash('No file attached to this assignment', 'error')
        return redirect(request.referrer or url_for('index'))
        
    try:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            assignment.file_path,
            as_attachment=True
        )
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(request.referrer or url_for('index'))

@teacher.route('/assignment/file/<path:filename>')
@login_required
def download_assignment_file_by_filename(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@teacher.route('/teacher/submission/<int:submission_id>/view')
@login_required
@teacher_required
def view_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    # Verify teacher has access to this submission
    if submission.assignment.course.teacher_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    return render_template('teacher/view_submission.html', 
                         submission=submission,
                         student=User.query.get(submission.student_id))

@teacher.route('/teacher/submission/download/<int:submission_id>')
@login_required
@teacher_required
def download_submission_file(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.assignment.course.teacher_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('teacher.dashboard'))
        
    if submission.file_path:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            submission.file_path,
            as_attachment=True
        )
    flash('No file attached to this submission', 'error')
    return redirect(url_for('teacher.view_submission', submission_id=submission_id))

@teacher.route('/teacher/messages')
@login_required
@teacher_required
def messages():
    course_students = db.session.query(User).join(CourseEnrollment)\
        .join(Course, Course.id == CourseEnrollment.course_id)\
        .filter(Course.teacher_id == current_user.id).distinct().all()
    
    # Получаем все непрочитанные сообщения для учителя
    unread_messages = Message.query.filter_by(
        receiver_id=current_user.id,
        read=False
    ).count()
    
    messages = Message.query.filter_by(receiver_id=current_user.id).all()
    
    return render_template('teacher/messages.html', 
                         students=course_students,
                         messages=messages,
                         unread_messages=unread_messages)

@teacher.route('/teacher/chat/<int:student_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def chat_with_student(student_id):
    student = User.query.get_or_404(student_id)
    
    # Отмечаем сообщения как прочитанные
    Message.query.filter_by(
        sender_id=student_id,
        receiver_id=current_user.id,
        read=False
    ).update({Message.read: True})
    
    if request.method == 'POST':
        content = request.form.get('message')
        if content:
            message = Message(
                sender_id=current_user.id,
                receiver_id=student_id,
                content=content
            )
            db.session.add(message)
    
    db.session.commit()
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == student_id)) |
        ((Message.sender_id == student_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at).all()
    
    return render_template('teacher/chat.html', 
                         other_user=student, 
                         messages=messages,
                         unread_messages=0)  # В чате все сообщения считаются прочитанными

@teacher.route('/teacher/statistics')
@login_required
@teacher_required
def course_statistics():
    # Получаем все курсы учителя
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    statistics = []
    
    for course in courses:
        # Получаем все оценки по этому курсу
        submissions = Submission.query.join(Assignment)\
            .filter(Assignment.course_id == course.id)\
            .filter(Submission.grade != None).all()
        
        if submissions:
            avg_grade = sum(s.grade for s in submissions) / len(submissions)
            total_students = db.session.query(CourseEnrollment)\
                .filter_by(course_id=course.id).count()
            graded_students = db.session.query(Submission.student_id.distinct())\
                .join(Assignment)\
                .filter(Assignment.course_id == course.id)\
                .filter(Submission.grade != None).count()
        else:
            avg_grade = 0
            total_students = 0
            graded_students = 0
            
        statistics.append({
            'course': course,
            'average_grade': round(avg_grade, 2),
            'total_students': total_students,
            'graded_students': graded_students,
            'submissions_count': len(submissions)
        })
    
    return render_template('teacher/statistics.html', statistics=statistics)

@teacher.route('/teacher/profile', methods=['GET', 'POST'])
@login_required
@teacher_required
def profile():
    if request.method == 'POST':
        try:
            current_user.full_name = request.form['full_name']
            current_user.email = request.form['email']
            
            # Проверка и обновление пароля
            if request.form.get('new_password'):
                if current_user.check_password(request.form['current_password']):
                    current_user.set_password(request.form['new_password'])
                else:
                    flash('Current password is incorrect', 'error')
                    return redirect(url_for('teacher.profile'))
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('teacher.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    return render_template('teacher/profile.html')
