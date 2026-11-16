from werkzeug.security import generate_password_hash
from app import connect_db, init_db

init_db()
print("Create your FindIt admin account")
name = input("Admin name: ").strip()
email = input("Admin email: ").strip().lower()
password = input("Admin password (at least 12 characters): ")
if not name or not email or len(password) < 12:
    print("Please provide a name, email and password of at least 12 characters.")
else:
    try:
        with connect_db() as db:
            db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,'admin')",
                       (name, email, generate_password_hash(password)))
        print("Admin account created. Start the app using: python app.py")
    except Exception as error:
        print("Could not create admin:", error)