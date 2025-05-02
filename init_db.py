from flask import Flask
from models import db, User
from config import Config

def create_admin():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        # Создаем таблицы
        db.create_all()
        
        # Проверяем существование админа
        if not User.is_admin_exists():
            admin = User(
                username='admin',
                email='admin@example.com',
                role='admin',
                full_name='System Administrator'
            )
            admin.set_password('admin123')  # Начальный пароль
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
        else:
            print("Admin user already exists!")

if __name__ == '__main__':
    create_admin()
