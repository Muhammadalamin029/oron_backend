import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings

def send_email(to_email: str, subject: str, html_content: str):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"Mock email to {to_email}: {subject}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to_email

    part1 = MIMEText(html_content, "html")
    msg.attach(part1)

    try:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")

def get_base_html_template(title: str, preheader: str, content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Inter', Helvetica, Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            .header {{ background-color: #09090b; padding: 24px; text-align: center; }}
            .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: -0.025em; font-family: serif; }}
            .content {{ padding: 32px; color: #3f3f46; line-height: 1.6; font-size: 16px; }}
            .footer {{ background-color: #fafafa; padding: 24px; text-align: center; color: #71717a; font-size: 14px; border-top: 1px solid #e4e4e7; }}
            .button {{ display: inline-block; padding: 12px 24px; background-color: #09090b; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: 500; margin-top: 24px; }}
            .preheader {{ display: none; max-height: 0px; overflow: hidden; }}
        </style>
    </head>
    <body>
        <div class="preheader">{preheader}</div>
        <div class="container">
            <div class="header">
                <h1>ORON</h1>
            </div>
            <div class="content">
                <h2 style="color: #09090b; margin-top: 0;">{title}</h2>
                {content}
            </div>
            <div class="footer">
                &copy; {settings.EMAILS_FROM_NAME}. All rights reserved.<br>
                This is an automated message, please do not reply.
            </div>
        </div>
    </body>
    </html>
    """

def send_verification_email(to_email: str, token: str):
    verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
    content = f"""
        <p>Welcome to ORON Watch Marketplace!</p>
        <p>Please verify your email address to unlock all features, including the ability to place active orders.</p>
        <div style="text-align: center;">
            <a href="{verify_url}" class="button">Verify My Email</a>
        </div>
        <p style="margin-top: 32px; font-size: 14px; color: #71717a;">
            Or copy and paste this link into your browser:<br>
            <a href="{verify_url}" style="color: #3b82f6;">{verify_url}</a>
        </p>
    """
    html_template = get_base_html_template(
        title="Verify Your Email",
        preheader="Confirm your email address to finish setting up your ORON account.",
        content=content
    )
    send_email(to_email, "Welcome to ORON! Please verify your email.", html_template)

def send_verify_and_set_password_email(to_email: str, token: str):
    set_password_url = f"{settings.FRONTEND_URL}/auth/set-password?token={token}"
    content = f"""
        <p>Welcome to ORON Watch Marketplace!</p>
        <p>We've received your order and are holding it for you. You're one step from tracking it: verify your email and set a password to access your order.</p>
        <div style="text-align: center;">
            <a href="{set_password_url}" class="button">Set My Password</a>
        </div>
        <p style="margin-top: 32px; font-size: 14px; color: #71717a;">
            Or copy and paste this link into your browser:<br>
            <a href="{set_password_url}" style="color: #3b82f6;">{set_password_url}</a>
        </p>
    """
    html_template = get_base_html_template(
        title="Verify Your Email & Set a Password",
        preheader="You're one step from tracking your ORON order.",
        content=content
    )
    send_email(to_email, "Welcome to ORON! Set a password to continue your order.", html_template)


def send_bank_transfer_details_email(to_email: str, order_id: str, bank_name: str, account_number: str, account_name: str, amount: float, expires_at):
    order_ref = order_id[-6:]
    expires_str = expires_at.strftime("%d %b %Y, %I:%M %p %Z") if expires_at else "shortly"
    amount_str = f"₦{amount:,.2f}"
    order_url = f"{settings.FRONTEND_URL}/orders/{order_id}"
    content = f"""
        <p>Complete your payment for order #{order_ref} by making a bank transfer for the exact amount below to the dedicated account number provided.</p>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>Bank:</strong> {bank_name or 'N/A'}</p>
            <p><strong>Account Number:</strong> {account_number or 'N/A'}</p>
            <p><strong>Account Name:</strong> {account_name or 'N/A'}</p>
            <p><strong>Amount:</strong> {amount_str}</p>
        </div>
        <p>This account number is valid until <strong>{expires_str}</strong>. Transfer the exact amount shown — your order will be marked paid automatically once we receive it.</p>
        <div style="text-align: center;">
            <a href="{order_url}" class="button">View Order</a>
        </div>
    """
    html_template = get_base_html_template(
        title="Complete Your Payment via Bank Transfer",
        preheader=f"Your dedicated account details for order #{order_ref}",
        content=content
    )
    send_email(to_email, "Complete Your Payment via Bank Transfer", html_template)


def send_bank_transfer_expired_email(to_email: str, order_id: str):
    order_ref = order_id[-6:]
    order_url = f"{settings.FRONTEND_URL}/orders/{order_id}"
    content = f"""
        <p>Your payment window for order #{order_ref} has expired without payment. No charge was made to any account.</p>
        <p>You can generate a new account number and complete your purchase at any time.</p>
        <div style="text-align: center;">
            <a href="{order_url}" class="button">Generate New Account Number</a>
        </div>
    """
    html_template = get_base_html_template(
        title="Payment Window Expired",
        preheader=f"Your payment window for order #{order_ref} has expired.",
        content=content
    )
    send_email(to_email, f"Payment Window Expired: Order #{order_ref}", html_template)


def send_notification_email(to_email: str, title: str, message: str):
    content = f"<p>{message}</p>"
    html_template = get_base_html_template(
        title=title,
        preheader=title,
        content=content
    )
    send_email(to_email, title, html_template)

def send_support_ticket_email(to_email: str, ticket_id: str, subject: str, message: str, is_admin: bool = False):
    if is_admin:
        title = f"New Support Ticket: {subject}"
        content = f"""
            <p>A new support ticket has been created:</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Ticket ID:</strong> {ticket_id}</p>
                <p><strong>Subject:</strong> {subject}</p>
                <p><strong>Message:</strong></p>
                <p style="font-style: italic;">{message}</p>
            </div>
            <p>Please log in to the admin dashboard to respond to this ticket.</p>
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/admin/support" class="button">View Ticket</a>
            </div>
        """
    else:
        title = f"Support Ticket Created: {subject}"
        content = f"""
            <p>Thank you for contacting ORON support! Your ticket has been created.</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Ticket ID:</strong> {ticket_id}</p>
                <p><strong>Subject:</strong> {subject}</p>
                <p><strong>Message:</strong></p>
                <p style="font-style: italic;">{message}</p>
            </div>
            <p>We'll review your ticket and respond as soon as possible. You can track the status of your ticket in your account.</p>
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/support" class="button">View Ticket</a>
            </div>
        """
    
    html_template = get_base_html_template(
        title=title,
        preheader=title,
        content=content
    )
    send_email(to_email, title, html_template)

def send_support_reply_email(to_email: str, ticket_id: str, subject: str, reply_message: str, sender_name: str, is_admin: bool = False):
    if is_admin:
        title = f"New Reply to Your Support Ticket: {subject}"
        content = f"""
            <p>You have received a reply to your support ticket from our team:</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Ticket ID:</strong> {ticket_id}</p>
                <p><strong>From:</strong> {sender_name}</p>
                <p><strong>Reply:</strong></p>
                <p style="font-style: italic;">{reply_message}</p>
            </div>
            <p>You can view the full conversation and reply in your account.</p>
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/support" class="button">View Ticket</a>
            </div>
        """
    else:
        title = f"Customer Reply to Support Ticket: {subject}"
        content = f"""
            <p>The customer has replied to the support ticket:</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Ticket ID:</strong> {ticket_id}</p>
                <p><strong>From:</strong> {sender_name}</p>
                <p><strong>Reply:</strong></p>
                <p style="font-style: italic;">{reply_message}</p>
            </div>
            <p>Please log in to the admin dashboard to respond.</p>
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/admin/support" class="button">View Ticket</a>
            </div>
        """
    
    html_template = get_base_html_template(
        title=title,
        preheader=title,
        content=content
    )
    send_email(to_email, title, html_template)

def send_dispute_email(to_email: str, dispute_id: str, order_id: str, reason: str, description: str, is_admin: bool = False):
    if is_admin:
        title = f"New Dispute Filed: Order #{order_id[-6:]}"
        content = f"""
            <p>A new dispute has been filed for an order:</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Dispute ID:</strong> {dispute_id}</p>
                <p><strong>Order ID:</strong> #{order_id[-6:]}</p>
                <p><strong>Reason:</strong> {reason}</p>
                <p><strong>Description:</strong></p>
                <p style="font-style: italic;">{description}</p>
            </div>
            <p>Please review this dispute and take appropriate action.</p>
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/admin/disputes" class="button">View Dispute</a>
            </div>
        """
    else:
        title = f"Dispute Filed: Order #{order_id[-6:]}"
        content = f"""
            <p>Your dispute has been successfully filed and is now under review.</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Dispute ID:</strong> {dispute_id}</p>
                <p><strong>Order ID:</strong> #{order_id[-6:]}</p>
                <p><strong>Reason:</strong> {reason}</p>
                <p><strong>Description:</strong></p>
                <p style="font-style: italic;">{description}</p>
            </div>
            <p>Our team will review your dispute and contact you with an update soon. You can track the status in your account.</p>
            <div style="text-align: center;">
                <a href="{settings.FRONTEND_URL}/disputes" class="button">View Dispute</a>
            </div>
        """
    
    html_template = get_base_html_template(
        title=title,
        preheader=title,
        content=content
    )
    send_email(to_email, title, html_template)
