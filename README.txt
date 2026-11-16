FINDIT — PYTHON-ONLY VERSION

You do NOT need Node.js, npm or React for this version.

SETUP
1. Extract the ZIP.
2. Open the FindIt_Python_Only folder in VS Code.
3. Open Terminal > New Terminal.
4. Run these commands one by one:

   python -m pip install -r requirements.txt
   python create_admin.py
   python app.py

5. The admin setup asks for a name, email and password (at least 12 characters).
6. Keep this terminal open.
7. Open Chrome and visit http://127.0.0.1:5000

STUDENT USE
- Click Register to create a student account.
- Log in with the student account.
- Submit LOST or FOUND reports.
- View possible matches for your lost reports.
- Submit an ownership claim with identifying details.

ADMIN USE
- Create the admin account using python create_admin.py before starting app.py.
- Log in using the admin email and password.
- Review claims and update their status.

IMPORTANT
- This is a local college demonstration prototype, not a production-ready service.
- Do not upload real sensitive personal information or publish it publicly.
- A matching score is only a suggestion, not proof of ownership.
- Admin must verify a claim before handing over an item.
- For public deployment, add stronger security, HTTPS, CSRF protection, rate limiting,
  secure secret-key configuration, privacy controls and secure file handling.
- Uploaded photos are stored locally in the uploads folder.
