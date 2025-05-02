from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, Course, Assignment, Submission, Material
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
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%dT%H:%M')
        
        assignment = Assignment(
            course_id=course_id,
            title=title,
            description=description,
            due_date=due_date
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Assignment created successfully!')
        
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
