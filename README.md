# WSPA - Web Student Progress Assessment

A web-based system for managing student assignments, submissions and course progress.

## Features
- Multiple user roles (Admin, Teacher, Student)
- Course management
- Assignment creation and submission
- File upload/download
- Student-teacher messaging
- Grade tracking
- Course statistics

## Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- SQLite3

## Installation

1. Clone the repository or unzip the project files:
```bash
git clone <repository-url>
# or unzip the files to your desired location
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

5. Create necessary directories:
```bash
mkdir uploads
mkdir uploads/assignments
mkdir uploads/submissions
```

## Initial Setup

1. Initialize the database and create admin user:
```bash
python init_db.py
```
This will create:
- SQLite database file (usos.db)
- Admin user with credentials:
  - Username: admin
  - Password: admin123

## Running the Application

1. Start the Flask development server:
```bash
python app.py
```

2. Access the application:
- Open a web browser and go to: http://127.0.0.1:5000
- Log in with admin credentials

## User Management

### Admin
- Can create/edit/delete users
- Can create/manage courses
- Can assign teachers to courses
- Can view system logs and statistics

### Teacher
- Can create assignments
- Can grade submissions
- Can message students
- Can view course statistics

### Student
- Can view and submit assignments
- Can view grades
- Can message teachers
- Can download course materials

## File Storage
Files are stored in:
- Assignments: `/uploads/assignments/`
- Submissions: `/uploads/submissions/`

## Security Notes
- Change the default admin password after first login
- In production, update SECRET_KEY in config.py
- Set up proper file upload restrictions
- Configure proper database backup

## Troubleshooting

1. Database Issues:
```bash
# Reset database
python init_db.py
```

2. File Permissions:
- Ensure the uploads directory is writable
- Check file ownership and permissions

3. Common Errors:
- "No module named 'flask'": Run `pip install -r requirements.txt`
- "No such file/directory": Create missing directories in /uploads/
- "Database locked": Close other connections to the database

## Project Structure
```
WSPA/
├── app.py              # Main application file
├── config.py           # Configuration settings
├── init_db.py         # Database initialization
├── models.py          # Database models
├── requirements.txt   # Python dependencies
├── routes/           # Route handlers
│   ├── admin.py
│   ├── teacher.py
│   └── student.py
├── templates/        # HTML templates
├── static/          # Static files
└── uploads/         # Uploaded files
    ├── assignments/
    └── submissions/
```
