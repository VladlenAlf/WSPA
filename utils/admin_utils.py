from functools import wraps
from flask import request
from models import db, SystemLog
from flask_login import current_user

def log_admin_action(action_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            log = SystemLog(
                user_id=current_user.id,
                action=action_name,
                details=str(request.form if request.form else request.args),
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            return result
        return decorated_function
    return decorator
