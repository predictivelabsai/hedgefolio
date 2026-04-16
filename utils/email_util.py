"""
Email utility using Postmark SDK.
Handles sending transactional emails for Hedge Fund Index.
"""

import os
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

POSTMARK_API_KEY = os.getenv("POSTMARK_API_KEY")
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL", "noreply@hedgefundindex.com")


def get_postmark_client():
    """Get Postmark client instance."""
    if not POSTMARK_API_KEY:
        raise ValueError("POSTMARK_API_KEY environment variable is not set")
    
    from postmarker.core import PostmarkClient
    return PostmarkClient(server_token=POSTMARK_API_KEY)


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    from_email: Optional[str] = None,
    tag: Optional[str] = None,
) -> Dict:
    """
    Send a single email via Postmark.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_body: HTML content of the email
        text_body: Plain text content (optional, will strip HTML if not provided)
        from_email: Sender email (defaults to POSTMARK_FROM_EMAIL)
        tag: Optional tag for tracking in Postmark
    
    Returns:
        Dict with send result including MessageID
    """
    client = get_postmark_client()
    
    if text_body is None:
        # Strip HTML tags for plain text version
        import re
        text_body = re.sub(r'<[^>]+>', '', html_body)
    
    response = client.emails.send(
        From=from_email or POSTMARK_FROM_EMAIL,
        To=to_email,
        Subject=subject,
        HtmlBody=html_body,
        TextBody=text_body,
        Tag=tag,
    )
    
    return {
        "success": True,
        "message_id": response.get("MessageID"),
        "to": to_email,
    }


def send_batch_emails(
    recipients: List[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    from_email: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Dict]:
    """
    Send batch emails via Postmark (up to 500 per batch).
    
    Args:
        recipients: List of recipient email addresses
        subject: Email subject line
        html_body: HTML content of the email
        text_body: Plain text content
        from_email: Sender email
        tag: Optional tag for tracking
    
    Returns:
        List of send results
    """
    client = get_postmark_client()
    
    if text_body is None:
        import re
        text_body = re.sub(r'<[^>]+>', '', html_body)
    
    # Postmark allows up to 500 emails per batch
    batch_size = 500
    results = []
    
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i + batch_size]
        
        messages = [
            {
                "From": from_email or POSTMARK_FROM_EMAIL,
                "To": email,
                "Subject": subject,
                "HtmlBody": html_body,
                "TextBody": text_body,
                "Tag": tag,
            }
            for email in batch
        ]
        
        responses = client.emails.send_batch(*messages)
        
        for response in responses:
            results.append({
                "success": response.get("ErrorCode") == 0,
                "message_id": response.get("MessageID"),
                "to": response.get("To"),
                "error": response.get("Message") if response.get("ErrorCode") != 0 else None,
            })
    
    return results


def send_welcome_email(to_email: str) -> Dict:
    """Send welcome email to new subscriber."""
    subject = "Welcome to Hedge Fund Index! 📊"
    
    html_body = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
            .button { display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin-top: 20px; }
            .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #888; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Welcome to Hedge Fund Index!</h1>
            </div>
            <div class="content">
                <p>Thanks for signing up! You're now subscribed to receive updates about:</p>
                <ul>
                    <li>📈 Latest hedge fund portfolio changes</li>
                    <li>🔥 Popular securities among institutional investors</li>
                    <li>📊 Market insights and analysis</li>
                </ul>
                <p>We analyze SEC 13F filings to help you understand what the world's top hedge funds are investing in.</p>
                <a href="https://hedgefundindex.com" class="button">Explore Now →</a>
            </div>
            <div class="footer">
                <p>You're receiving this because you signed up at Hedge Fund Index.</p>
                <p>To unsubscribe, reply to this email with "unsubscribe".</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        tag="welcome",
    )


def send_newsletter(
    recipients: List[str],
    subject: str,
    content: str,
    tag: str = "newsletter",
) -> List[Dict]:
    """Send newsletter to all subscribers."""
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #888; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Hedge Fund Index Update</h1>
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                <p>You're receiving this because you signed up at Hedge Fund Index.</p>
                <p>To unsubscribe, reply to this email with "unsubscribe".</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_batch_emails(
        recipients=recipients,
        subject=subject,
        html_body=html_body,
        tag=tag,
    )


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# Test function
if __name__ == "__main__":
    print("Email utility loaded.")
    print(f"POSTMARK_API_KEY configured: {bool(POSTMARK_API_KEY)}")
    print(f"From email: {POSTMARK_FROM_EMAIL}")
    
    # Test email validation
    test_emails = ["test@example.com", "invalid-email", "user@domain.co.uk"]
    for email in test_emails:
        print(f"  {email}: {'✓' if validate_email(email) else '✗'}")


