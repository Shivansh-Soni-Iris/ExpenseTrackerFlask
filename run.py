from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv
load_dotenv()


app = create_app()

with app.app_context():
    db.create_all()

    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')

    if not User.query.filter_by(username=admin_username).first():
        admin = User(
            username=admin_username,
            password=generate_password_hash(admin_password),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created.")
    else:
        print("Admin user already exists.")

if __name__ == "__main__":
    app.run(debug=True)