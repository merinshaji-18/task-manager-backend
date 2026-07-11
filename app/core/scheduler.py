from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.database.connection import SessionLocal
from app.models.task import Task, Notification
from app.models.user import User

def check_deadlines():
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        # --- 1. UPCOMING LOGS (24h WARNING) ---
        # Look for tasks due in the next 24 hours that haven't sent a warning yet
        warning_window = now + timedelta(hours=24)
        upcoming_tasks = db.query(Task).filter(
            Task.due_date <= warning_window,
            Task.due_date > now,
            Task.status == 'pending',
            (Task.notification_sent == False) | (Task.notification_sent.is_(None))
        ).all()

        for task in upcoming_tasks:
            new_notif = Notification(
                user_id=task.owner_id,
                task_id=task.id,
                message=f"UPCOMING: '{task.title}' is due within 24 hours."
            )
            db.add(new_notif)
            task.notification_sent = True # Mark that the 24h warning is sent
            db.commit()
            print(f"Intelligence: Warning sent for {task.title}")


        # --- 2. COMPROMISED LOGS (OVERDUE ALERT) ---
        # Look for tasks where the deadline has passed but status is still pending
        overdue_tasks = db.query(Task).filter(
            Task.due_date < now,
            Task.status == 'pending'
        ).all()

        for task in overdue_tasks:
            # Check if we already created a 'Compromised' alert to avoid spamming every minute
            already_notified = db.query(Notification).filter(
                Notification.task_id == task.id,
                Notification.message.like("OBJECTIVE COMPROMISED%")
            ).first()

            if not already_notified:
                new_notif = Notification(
                    user_id=task.owner_id,
                    task_id=task.id,
                    message=f"OBJECTIVE COMPROMISED: '{task.title}' missed target deadline."
                )
                db.add(new_notif)
                db.commit()
                print(f"Intelligence: Compromised alert sent for {task.title}")

        # --- 3. PROGRESS STALLED (OPTIONAL: INERTIA ALERT) ---
        # If task is 6 hours away and 0% subtasks are done
        inertia_window = now + timedelta(hours=6)
        stalled_tasks = db.query(Task).filter(
            Task.due_date <= inertia_window,
            Task.due_date > now,
            Task.status == 'pending'
        ).all()

        for task in stalled_tasks:
            # Only alert if task has subtasks and none are finished
            if task.sub_tasks and len([s for s in task.sub_tasks if s.is_completed]) == 0:
                already_stalled = db.query(Notification).filter(
                    Notification.task_id == task.id,
                    Notification.message.like("INERTIA ALERT%")
                ).first()
                
                if not already_stalled:
                    new_notif = Notification(
                        user_id=task.owner_id,
                        task_id=task.id,
                        message=f"INERTIA ALERT: No progress detected on '{task.title}'."
                    )
                    db.add(new_notif)
                    db.commit()

    except Exception as e:
        print(f"Scheduler Error: {e}")
    finally:
        db.close()

# Run every 1 minute
scheduler = BackgroundScheduler()
scheduler.add_job(check_deadlines, 'interval', minutes=1)