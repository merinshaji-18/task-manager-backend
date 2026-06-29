from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import timedelta
import google.auth.transport.requests
from datetime import datetime, timedelta, timezone
from app.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]
def create_google_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [
                    settings.GOOGLE_REDIRECT_URI
                ],}},
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
def get_calendar_service(user):
    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,)
    if credentials.expired and credentials.refresh_token:
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        
    return build("calendar", "v3", credentials=credentials)

# app/core/google_calendar.py

def create_calendar_event(user, task):
    if not task.due_date:
        return None
    
    service = get_calendar_service(user)
    
    # ISSUE 1 FIX: Added Client Name [Category] to the Summary
    summary = f"[{task.category}] {task.title}" if task.category else task.title
    
    start_time = task.due_date.isoformat()
    end_time = (task.due_date + timedelta(hours=1)).isoformat()

    event = {
        "summary": summary,
        "description": task.description or "Created via Task Manager",
        "start": {"dateTime": start_time, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_time, "timeZone": "Asia/Kolkata"},
    }
    
    result = service.events().insert(calendarId="primary", body=event).execute()
    return result.get('id')

# ISSUE 2 FIX: Update Event
def update_calendar_event(user, task):
    if not task.google_event_id or not task.due_date:
        return
    try:
        service = get_calendar_service(user)
        summary = f"[{task.category}] {task.title}" if task.category else task.title
        event = {
            "summary": summary,
            "description": task.description or "",
            "start": {"dateTime": task.due_date.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": (task.due_date + timedelta(hours=1)).isoformat(), "timeZone": "Asia/Kolkata"},
        }
        service.events().update(calendarId="primary", eventId=task.google_event_id, body=event).execute()
    except Exception as e:
        print(f"Update failed: {e}")

# ISSUE 2 FIX: Delete Event
def delete_calendar_event(user, task):
    if not task.google_event_id:
        return
    try:
        service = get_calendar_service(user)
        service.events().delete(calendarId="primary", eventId=task.google_event_id).execute()
    except Exception as e:
        print(f"Delete failed: {e}")