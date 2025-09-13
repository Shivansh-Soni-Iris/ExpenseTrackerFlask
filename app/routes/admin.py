from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__)

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required')
            return redirect(url_for('expenses.dashboard'))
        return func(*args, **kwargs)
    return wrapper

@admin_bp.route('/admin/users')
@login_required
@admin_required
def manage_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    return render_template('admin_dashboard.html', users=users)


@admin_bp.route('/admin/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.is_admin = 'is_admin' in request.form
        new_password = request.form.get('new_password')
        if new_password:
            user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('User updated')
        return redirect(url_for('admin.manage_users'))
    return render_template('edit_user.html', user=user)