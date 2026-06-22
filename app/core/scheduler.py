from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.database.connection import SessionLocal
from app.models.task import Task
from app.models.user import User
import smtplib
from email.mime.text import MIMEText
from app.core.config import settings

def send_deadline_email(user_email, task_title, due_time):
    sender_email = "taskmanagerworkspace@gmail.com"
    msg = MIMEText(f"CRITICAL ALERT: Your objective '{task_title}' is reaching its deadline at {due_time}. Please ensure all parameters are met.")
    msg['Subject'] = f"⚠️ DEADLINE ALERT: {task_title}"
    msg['From'] = f"Workspace <{sender_email}>"
    msg['To'] = user_email

    try:
        with smtplib.SMTP("smtp-relay.brevo.com", 587) as server:
            server.starttls()
            server.login("ae70ae001@smtp-brevo.com", settings.BREVO_API_KEY)
            server.send_message(msg)
    except Exception as e:
        print(f"Notification Error: {e}")

def check_deadlines():
    db: Session = SessionLocal()
    print("--- DEBUG: Scheduler Heartbeat Running ---") # Add this
    try:
        now = datetime.now(timezone.utc)
        # CHANGE: Look 48 hours ahead instead of 1
        test_window = now + timedelta(hours=48) 
        
        upcoming_tasks = db.query(Task).filter(
            Task.due_date <= test_window,
            Task.due_date > now,
            Task.status == 'pending',
            # This handles the NULLs you have in your DB
            (Task.notification_sent == False) | (Task.notification_sent.is_(None))
        ).all()

        print(f"DEBUG: Found {len(upcoming_tasks)} tasks in the window.")

        for task in upcoming_tasks:
            user = db.query(User).filter(User.id == task.owner_id).first()
            if user:
                send_deadline_email(user.email, task.title, task.due_date.strftime("%d-%m-%Y %H:%M"))
                task.notification_sent = True
                db.commit()
                print(f"SUCCESS: Notification dispatched to {user.email}")
    finally:
        db.close()

# CHANGE: Run every 1 minute so you don't have to wait
scheduler = BackgroundScheduler()
scheduler.add_job(check_deadlines, 'interval', minutes=1)

