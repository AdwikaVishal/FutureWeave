"""
Celery tasks for longitudinal tracking and follow-up emails.
"""
from celery import Celery
from celery.signals import worker_ready
import os

# Configure Celery with Redis broker
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
app = Celery('tasks', broker=REDIS_URL, backend=REDIS_URL)

# Optional: SendGrid email
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")


def get_sendgrid_client():
    """Lazy import and initialize SendGrid client."""
    if not SENDGRID_API_KEY:
        return None
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        return sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
    except ImportError:
        return None


@app.task(bind=True, max_retries=3)
def send_followup_email(self, simulation_id: int, user_email: str, decision: str):
    """
    Send a follow-up email 6 months after simulation.
    """
    if not user_email:
        print(f"[FollowUp] No email provided for simulation {simulation_id}, skipping.")
        return {"status": "skipped", "reason": "no_email"}
    
    sg = get_sendgrid_client()
    if not sg:
        print(f"[FollowUp] SendGrid not configured. Would send to {user_email} about: {decision}")
        return {"status": "skipped", "reason": "sendgrid_not_configured"}
    
    try:
        from sendgrid.helpers.mail import Mail
        
        # Build the follow-up URL
        base_url = os.environ.get("APP_BASE_URL", "http://localhost:3000")
        followup_url = f"{base_url}/followup/{simulation_id}"
        
        message = Mail(
            from_email='noreply@decisionsim.com',
            to_emails=user_email,
            subject='Which timeline are you living in?',
            html_content=f'''
            <p>Hi there,</p>
            <p>6 months ago, you used FutureWeave to explore:</p>
            <blockquote style="border-left: 3px solid #ccc; padding-left: 10px; margin: 10px 0;">
                {decision}
            </blockquote>
            <p>We'd love to know — which timeline are you living in now?</p>
            <p><a href="{followup_url}" style="display:inline-block;padding:10px 20px;background:#4CAF50;color:white;text-decoration:none;border-radius:5px;">
                Tell us how it went
            </a></p>
            <p>Your insights help others make better decisions.</p>
            <p>— FutureWeave</p>
            '''
        )
        
        response = sg.send(message)
        print(f"[FollowUp] Email sent to {user_email}, status: {response.status_code}")
        return {"status": "sent", "simulation_id": simulation_id}
        
    except Exception as exc:
        print(f"[FollowUp] Failed to send email: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@app.task
def schedule_followup(simulation_id: int, user_email: str, decision: str):
    """
    Schedule the follow-up email to be sent in ~6 months (180 days).
    For testing, you can override with FOLLOWUP_DAYS env var.
    """
    days = int(os.environ.get("FOLLOWUP_DAYS", "180"))
    countdown = days * 24 * 3600  # Convert days to seconds
    
    send_followup_email.apply_async(
        args=[simulation_id, user_email, decision],
        countdown=countdown
    )
    
    print(f"[FollowUp] Scheduled follow-up for simulation {simulation_id} in {days} days")
    return {"status": "scheduled", "simulation_id": simulation_id, "days": days}

