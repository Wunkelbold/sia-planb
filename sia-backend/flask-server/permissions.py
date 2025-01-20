from globals import app
from database import Tables
from functools import wraps
from fnmatch import fnmatch
from flask_login import login_required, current_user


def hasPermissions(*permissions_required: str) -> bool:
    if not permissions_required: return True
    if not current_user.is_authenticated: return  False
    
    userRolePermissions = Tables.Role.query.filter_by(name=current_user.role).first().permissions
    userPermissions = userRolePermissions + current_user.permissions

    for permission_required in permissions_required:
        match = False
        for permission in userPermissions:
            if fnmatch(permission_required, permission):
                match = True
                break
        if not match: return False
    return True


def require_permissions(*permissions_required: str):
    def decorator(function):
        @login_required
        @wraps(function)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs) if hasPermissions(*permissions_required) else app.login_manager.unauthorized()
        return wrapper
    return decorator

@app.context_processor
def attachPermissionsToRenderer():
    return dict(hasPermissions=hasPermissions)