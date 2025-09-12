from flask import Flask, render_template, redirect, url_for, request, flash, send_file, make_response, abort
from flask_login import (
    LoginManager, login_required, UserMixin,
    current_user, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from collections import defaultdict
import csv
from reportlab.pdfgen import canvas
from io import BytesIO
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ---------------- App Config ----------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Database path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, 'expense.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- Login Manager ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------- Category Info ----------------
CATEGORY_INFO = {
    "food": {"icon": "🍔", "color": "#FF6384"},
    "transport": {"icon": "🚌", "color": "#36A2EB"},
    "shopping": {"icon": "🛍️", "color": "#FFCE56"},
    "bills": {"icon": "💡", "color": "#4BC0C0"},
    "entertainment": {"icon": "🎬", "color": "#9966FF"},
    "toy": {"icon": "🧸", "color": "#42BFD8"},
    "other": {"icon": "📦", "color": "#FF9F40"},
}

# ---------------- Models ----------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    expenses = db.relationship('Expense', backref='owner', lazy=True)
    is_admin = db.Column(db.Boolean, default=False)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


def create_admin():
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    existing = User.query.filter_by(username=admin_username).first()
    if not existing:
        admin = User(
            username=admin_username,
            password=generate_password_hash(admin_password),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created")


# ---------------- Decorators ----------------
def admin_required(f):
    def wrap(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap


# ---------------- Routes ----------------
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# -------- Authentication --------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration Successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


# -------- Dashboard --------
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for("admin_dashboard"))

    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    category_data = defaultdict(float)
    for e in expenses:
        category_data[e.category.lower()] += float(e.amount)

    trend_data = defaultdict(float)
    for e in expenses:
        month = e.date.strftime("%Y-%m")
        trend_data[month] += float(e.amount)
    trend_data = dict(sorted(trend_data.items()))

    total_spent = sum(float(e.amount) for e in expenses)
    average_expense = round(total_spent / len(expenses), 2) if expenses else 0
    highest_category = max(category_data, key=category_data.get) if category_data else "N/A"

    return render_template(
        'dashboard.html',
        expenses=expenses,
        category_data=category_data,
        trend_data=trend_data,
        total_spent=total_spent,
        average_expense=average_expense,
        highest_category=highest_category,
        category_info=CATEGORY_INFO
    )


# -------- Add Expense --------
@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category'].lower()
        description = request.form['description']
        new_expense = Expense(amount=amount, category=category,
                              description=description, user_id=current_user.id)
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_expense.html')


# -------- Delete Expense --------
@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_user.id:
        flash("Not authorized to delete this expense.", "danger")
        return redirect(url_for('dashboard'))

    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted successfully.", "success")
    return redirect(url_for('dashboard'))


# -------- Change Password --------
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not check_password_hash(current_user.password, current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('change_password'))

        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for('dashboard'))

    return render_template("change_password.html")


# -------- Export CSV --------
@app.route('/export/csv')
@login_required
def export_csv():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    output = BytesIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Category', 'Description', 'Amount'])
    for e in expenses:
        writer.writerow([e.date.strftime('%Y-%m-%d'),
                        e.category, e.description, "%.2f" % e.amount])

    output.seek(0)
    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    response.headers["Content-type"] = "text/csv"
    return response


# -------- Export PDF --------
@app.route('/export/pdf')
@login_required
def export_pdf():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Expenses Report")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 800, "Expenses Report")

    pdf.setFont("Helvetica", 12)
    y = 760
    pdf.drawString(50, y, "Date")
    pdf.drawString(150, y, "Category")
    pdf.drawString(300, y, "Description")
    pdf.drawString(450, y, "Amount (₹)")
    y -= 20

    for e in expenses:
        if y < 50:
            pdf.showPage()
            y = 800
        pdf.drawString(50, y, e.date.strftime('%Y-%m-%d'))
        pdf.drawString(150, y, e.category)
        pdf.drawString(300, y, e.description[:25] if e.description else "")
        pdf.drawString(450, y, "%.2f" % e.amount)
        y -= 20

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="expenses.pdf", mimetype='application/pdf')


# -------- Admin Section --------
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    return render_template("admin_dashboard.html", users=users)


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        new_username = request.form["username"]
        new_password = request.form.get("password")

        user.username = new_username
        if new_password:
            user.password = generate_password_hash(new_password)

        db.session.commit()
        flash("User updated successfully!", "success")
        return redirect(url_for("admin_users"))

    return render_template("edit_user.html", user=user)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully!", "success")
    return redirect(url_for("admin_users"))


# ---------------- Main ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(debug=True)
