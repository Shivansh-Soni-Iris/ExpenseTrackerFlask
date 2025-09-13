from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Expense
from datetime import datetime, date

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/')
@login_required
def dashboard():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    categories = {}
    for exp in expenses:
        categories[exp.category] = categories.get(exp.category, 0) + exp.amount
    today = date.today().isoformat() 
    return render_template('dashboard.html', expenses=expenses, chart_data=categories,current_date=today)

@expenses_bp.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    data = request.form
    new_expense = Expense(
        amount=float(data['amount']),
        category=data['category'],
        description=data['description'],
        date=datetime.strptime(data['date'], '%Y-%m-%d'),
        user_id=current_user.id
    )
    db.session.add(new_expense)
    db.session.commit()
    return redirect(url_for('expenses.dashboard'))

@expenses_bp.route('/delete_expense/<int:id>')
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id == current_user.id or current_user.is_admin:
        db.session.delete(expense)
        db.session.commit()
    return redirect(url_for('expenses.dashboard'))