import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from dotenv import load_dotenv
load_dotenv()


DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_HOST_PORT = os.getenv("EMAIL_HOST_PORT",587)
EMAIL_USE_TLS = True


def send_email(recipient_email, subject, body, html_body=None, attachments=None):
    """
    Send an email using SMTP with support for both plain text and HTML content

    Parameters:
    - recipient_email: Email address of the recipient
    - subject: Subject of the email
    - body: Plain text body of the email (fallback for non-HTML clients)
    - html_body: HTML body of the email (optional, for rich formatting)
    - attachments: List of file paths to attach (default: None)

    Returns:
    - True if the email was sent successfully, False otherwise
    """
    try:
        # Create a multipart message
        message = MIMEMultipart("alternative")
        message["From"] = DEFAULT_FROM_EMAIL
        message["To"] = recipient_email
        message["Subject"] = subject

        # Create plain text part
        text_part = MIMEText(body, "plain")
        message.attach(text_part)

        # Create HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, "html")
            message.attach(html_part)

        # If we have attachments, we need to restructure the message
        if attachments:
            # Create a new multipart message for mixed content
            mixed_message = MIMEMultipart("mixed")
            mixed_message["From"] = DEFAULT_FROM_EMAIL
            mixed_message["To"] = recipient_email
            mixed_message["Subject"] = subject

            # Attach the alternative message (text/html) to the mixed message
            mixed_message.attach(message)

            # Add attachments
            for file_path in attachments:
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as file:
                        part = MIMEApplication(file.read(), Name=os.path.basename(file_path))

                    # Add header to attachment
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    mixed_message.attach(part)

            # Use the mixed message instead
            message = mixed_message

        # Create SMTP session
        with smtplib.SMTP(EMAIL_HOST, int(EMAIL_HOST_PORT)) as server:
            # Start TLS for security
            server.starttls()

            # Login to sender's email
            server.login(DEFAULT_FROM_EMAIL, EMAIL_HOST_PASSWORD)

            # Send the email
            server.send_message(message)

        print("Email sent successfully!")
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def create_html_template(title, content, styles=None):
    """
    Helper function to create a well-styled HTML email template

    Parameters:
    - title: Title for the email
    - content: Main HTML content
    - styles: Additional CSS styles (optional)

    Returns:
    - Complete HTML string ready for email
    """
    default_styles = """
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }
        .email-container {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .header {
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #007bff;
            margin: 0;
            font-size: 24px;
        }
        .content {
            margin-bottom: 30px;
        }
        .button {
            display: inline-block;
            padding: 12px 24px;
            background-color: #007bff;
            color: #ffffff !important;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin: 10px 0;
        }
        .button:hover {
            background-color: #0056b3;
        }
        .footer {
            border-top: 1px solid #dddddd;
            padding-top: 20px;
            font-size: 12px;
            color: #666666;
            text-align: center;
        }
        .highlight {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
    """

    if styles:
        default_styles += styles

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            {default_styles}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                <p>This email was sent automatically. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html_template


# Example usage functions
def send_welcome_email(recipient_email, user_name):
    """Example: Send a styled welcome email"""

    subject = f"Welcome to our platform, {user_name}!"

    # Plain text version
    plain_text = f"""
    Welcome {user_name}!

    Thank you for joining our platform. We're excited to have you on board!

    To get started, please verify your email address by clicking the link below.

    Best regards,
    The Team
    """

    # HTML version
    html_content = f"""
        <h2>Welcome {user_name}!</h2>
        <p>Thank you for joining our platform. We're excited to have you on board!</p>

        <div class="highlight">
            <p><strong>Next Steps:</strong></p>
            <ul>
                <li>Verify your email address</li>
                <li>Complete your profile</li>
                <li>Explore our features</li>
            </ul>
        </div>

        <p>To get started, please verify your email address:</p>
        <a href="#" class="button">Verify Email Address</a>

        <p>If you have any questions, feel free to reach out to our support team.</p>

        <p>Best regards,<br>The Team</p>
    """

    html_body = create_html_template("Welcome!", html_content)

    return send_email(recipient_email, subject, plain_text, html_body)


def send_notification_email(recipient_email, notification_title, notification_message):
    """Example: Send a styled notification email"""

    subject = f"Notification: {notification_title}"

    # Plain text version
    plain_text = f"""
    {notification_title}

    {notification_message}

    Best regards,
    The Team
    """

    # HTML version
    html_content = f"""
        <h2>{notification_title}</h2>
        <p>{notification_message}</p>

        <div class="highlight">
            <p><strong>Important:</strong> This notification requires your attention.</p>
        </div>

        <a href="#" class="button">View Details</a>

        <p>Thank you for your attention.</p>
    """

    html_body = create_html_template("Notification", html_content)

    return send_email(recipient_email, subject, plain_text, html_body)
