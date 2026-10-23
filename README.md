# Task Manager (Flask + MySQL)

A beginner-friendly web app: add, complete and delete tasks.

## 1. Set up MySQL
Install MySQL Server (https://dev.mysql.com/downloads/) and remember the root password.
Then create the database (MySQL Workbench or terminal):

    mysql -u root -p < schema.sql

## 2. Run in VS Code
1. Install Python 3.9+ and VS Code (with the "Python" extension).
2. File > Open Folder > select this folder.
3. Copy `.env.example` to `.env` and put your MySQL password in it.
4. Open the terminal (Ctrl + `) and run:

       python -m venv .venv
       # Windows:   .venv\Scripts\activate
       # Mac/Linux: source .venv/bin/activate
       pip install -r requirements.txt
       python app.py

5. Open http://127.0.0.1:5000 in your browser.

## 3. Deploy
You need two things: a hosted MySQL database and a host for the app.

1. Create a hosted MySQL database (for example Aiven, Railway or TiDB Cloud;
   check which one currently has a free tier). Note the host, port, user,
   password, database name and CA certificate if they give one.
2. Push this folder to GitHub (the .env file is git-ignored, so secrets stay safe).
3. On render.com: New > Web Service > connect the repo.
   - Build command: pip install -r requirements.txt
   - Start command: gunicorn app:app
4. Under Environment, add DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
   (and DB_SSL_CA if needed) with your hosted database values.
5. Deploy. You get a public URL.

## Common errors
- "Access denied for user": wrong DB_USER or DB_PASSWORD in .env
- "Unknown database 'taskdb'": run schema.sql first
- "Can't connect to MySQL server": MySQL isn't running, or DB_HOST/DB_PORT is wrong

## Ideas to extend
- Due dates and priorities
- User login (Flask-Login)
- Edit existing tasks
- Switch to SQLAlchemy
- Tests with pytest
