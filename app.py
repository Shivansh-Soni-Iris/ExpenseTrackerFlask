from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from collections import defaultdict
import csv
from flask import make_response
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Database path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'instance')  # ensure this folder exists
os.makedirs(DB_DIR, exist_ok=True)            # create if missing

DB_PATH = os.path.join(DB_DIR, 'expense.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    expenses = db.relationship('Expense', backref='owner', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ---------------- Routes ----------------
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

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
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        flash('Invalid Credentials!', 'danger')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# -------- Dashboard --------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    expenses = Expense.query.filter_by(user_id=user.id).all()

    # ----- Category Data -----
    category_data = defaultdict(float)
    for e in expenses:
        category_data[e.category] += float(e.amount)

    # ----- Trend Data (monthly) -----
    trend_data = defaultdict(float)
    for e in expenses:
        month = e.date.strftime("%Y-%m")
        trend_data[month] += float(e.amount)
    trend_data = dict(sorted(trend_data.items()))

    # ----- Summary Cards -----
    total_spent = sum(float(e.amount) for e in expenses)
    average_expense = round(total_spent / len(expenses), 2) if expenses else 0

    if category_data:
        highest_category = max(category_data, key=category_data.get)
    else:
        highest_category = "N/A"

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
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']
        description = request.form['description']
        new_expense = Expense(amount=amount, category=category, description=description, user_id=session['user_id'])
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_expense.html')

# ----- Export CSV -----
@app.route('/export/csv')
def export_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    expenses = Expense.query.filter_by(user_id=session['user_id']).all()

    # Create CSV in memory
    si = BytesIO()
    output = si
    writer = csv.writer(output)
    writer.writerow(['Date', 'Category', 'Description', 'Amount'])
    for e in expenses:
        writer.writerow([e.date.strftime('%Y-%m-%d'), e.category, e.description, "%.2f" % e.amount])

    output.seek(0)
    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# ----- Export PDF -----
@app.route('/export/pdf')
def export_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    expenses = Expense.query.filter_by(user_id=session['user_id']).all()
    
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
        if y < 50:  # New page if we reach bottom
            pdf.showPage()
            y = 800
        pdf.drawString(50, y, e.date.strftime('%Y-%m-%d'))
        pdf.drawString(150, y, e.category)
        pdf.drawString(300, y, e.description[:25])  # truncate if too long
        pdf.drawString(450, y, "%.2f" % e.amount)
        y -= 20

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="expenses.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create DB tables
    app.run(debug=True)
