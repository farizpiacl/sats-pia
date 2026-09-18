from functools import wraps
from flask import abort
from flask_login import current_user


def roles_required(*roles):
    """Restrict a view to users whose role is in `roles`.

    Usage:
        @roles_required(UserRole.SUPER_ADMIN)
        def my_view(): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def super_admin_required(view_func):
    from app.models.user import UserRole

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if current_user.role != UserRole.SUPER_ADMIN:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped
