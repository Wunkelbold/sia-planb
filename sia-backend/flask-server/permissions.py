from globals import app
from database import Tables
from functools import wraps
from flask_login import login_required, current_user


def hasPermissions(*permissions_required: str) -> bool:
    if not current_user.is_authenticated: return False
    userRolePermissions = Tables.Role.query.filter_by(name=current_user.role).first().permissions
    userPermissions = userRolePermissions + current_user.permissions
    return all(permission in userPermissions for permission in permissions_required)


def require_permissions(*permissions_required: str):
    def decorator(function):
        @login_required
        @wraps(function)
        def wrapper(*args, **kwargs):
            from app import app
            return function(*args, **kwargs) if hasPermissions(*permissions_required) else app.login_manager.unauthorized()
        return wrapper
    return decorator

@app.context_processor
def attachPermissionsToRenderer():
    return dict(hasPermissions=hasPermissions)