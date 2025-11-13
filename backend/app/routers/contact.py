from fastapi import APIRouter, Form, HTTPException
import os
from app.services.email import EmailConfig, EmailService

router = APIRouter()

@router.post("/contact/")
def submit_contact(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    subject: str = Form(...),
    message: str = Form(...),
):
    """Receive contact form submissions from the website and email them to the configured recipient.

    Expects application/x-www-form-urlencoded form data (the static `contact.html` form).
    """
    cfg = EmailConfig.from_env()
    svc = EmailService(cfg)

    recipient = os.getenv("CONTACT_RECIPIENT") or cfg.default_from or cfg.smtp_user
    if not recipient:
        raise HTTPException(status_code=500, detail="Contact recipient not configured")

    body_lines = [
        f"Name: {name}",
        f"Email: {email}",
        f"Phone: {phone or ''}",
        "",
        "Message:",
        message,
    ]
    body = "\n".join(body_lines)

    try:
        svc.send_email(
            to_addresses=[recipient],
            subject=f"Website contact: {subject}",
            body=body,
            from_address=cfg.default_from or recipient,
            reply_to=email,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send contact email: {e}")

    return {"status": "ok", "message": "Contact message sent"}
