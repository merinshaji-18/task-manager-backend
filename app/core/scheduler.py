from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.database.connection import SessionLocal
from app.models.task import Task
from app.models.user import User
import smtplib
from email.mime.text import MIMEText
from app.core.config import settings


def check_deadlines():
    db: Session = SessionLocal()
    print("--- DEBUG: Scheduler Heartbeat Running ---") # Add this
    try:
        now = datetime.now(timezone.utc)
        # CHANGE: Look 48 hours ahead instead of 1
        test_window = now + timedelta(hours=48) 
        
        print(f"NOW: {now}")
        print(f"WINDOW END: {test_window}")

        all_tasks = db.query(Task).all()

        print(f"TOTAL TASKS IN DB: {len(all_tasks)}")

        for task in all_tasks:
            print(
                f"Task={task.title} | "
                f"Due={task.due_date} | "
                f"Status={task.status} | "
                f"Notification={task.notification_sent}"
            )
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
                task.notification_sent = True
                db.commit()
    finally:
        db.close()

# CHANGE: Run every 1 minute so you don't have to wait
scheduler = BackgroundScheduler()
scheduler.add_job(check_deadlines, 'interval', minutes=1)

