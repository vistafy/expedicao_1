from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            flash("⛔ Acesso restrito a administradores.", "erro")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function
