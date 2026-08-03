import logging
from typing import Optional
import html as html_lib

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailSender:
    """Sends via Brevo's HTTP API (port 443) rather than raw SMTP — hosts
    like Render block or silently drop outbound SMTP ports (25/465/587),
    but HTTPS always works, so this sidesteps that class of failure entirely."""

    def __init__(self):
        self.api_key = settings.BREVO_API_KEY
        self.from_email = settings.EMAILS_FROM_EMAIL
        self.from_name = settings.EMAILS_FROM_NAME

    async def send_email_async(self, to_email, subject, html_body, text_body=None) -> bool:
        if not self.api_key:
            logger.info(f"Mock email to {to_email}: {subject}")
            return True

        payload = {
            "sender": {"name": self.from_name, "email": self.from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
        }
        if text_body:
            payload["textContent"] = text_body

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(BREVO_API_URL, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(
                    f"Failed to send email to {to_email}: Brevo API {response.status_code} {response.text}"
                )
                return False
            logger.info(f"Email sent to {to_email}")
            return True
        except httpx.RequestError as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False


_sender = EmailSender()


async def send_email(to_email: str, subject: str, html_content: str):
    await _sender.send_email_async(to_email, subject, html_content)


def get_base_html_template(title: str, preheader: str, content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #0e0e0e; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #111111; border: 1px solid #353534; border-radius: 8px; overflow: hidden; }}
            .header {{ background-color: #131313; padding: 28px 24px; text-align: center; border-bottom: 2px solid #ff6b00; }}
            .header h1 {{ color: #ffffff; margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.2em; }}
            .header h1 span {{ color: #ff6b00; }}
            .content {{ padding: 32px; color: #e5e2e1; line-height: 1.6; font-size: 16px; }}
            .footer {{ background-color: #0e0e0e; padding: 24px; text-align: center; color: #9a9898; font-size: 13px; border-top: 1px solid #353534; }}
            .button {{ display: inline-block; padding: 14px 28px; background-color: #ff6b00; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; font-size: 13px; margin-top: 24px; }}
            .preheader {{ display: none; max-height: 0px; overflow: hidden; }}
            a {{ color: #ff6b00; }}
        </style>
    </head>
    <body>
        <div class="preheader">{preheader}</div>
        <div class="container">
            <div class="header">
                <h1>ORON <span>TECHWARE</span></h1>
            </div>
            <div class="content">
                <h2 style="color: #ffffff; margin-top: 0;">{title}</h2>
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


def _render_order_items_html(items: list) -> str:
    """items: list of {"name": str, "quantity": int, "price": float}. Empty/None renders nothing."""
    if not items:
        return ""
    rows = "".join(f"""
        <tr>
            <td style="padding: 8px 0; border-bottom: 1px solid #353534;">{item['name']} &times; {item['quantity']}</td>
            <td style="padding: 8px 0; border-bottom: 1px solid #353534; text-align: right;">₦{item['price'] * item['quantity']:,.2f}</td>
        </tr>""" for item in items)
    return f"""
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            {rows}
        </table>
    """


def _render_shipping_html(shipping_info) -> str:
    """shipping_info: dict with first_name/last_name/phone/address/city/state, or None."""
    if not shipping_info:
        return ""
    name = f"{shipping_info.get('first_name', '')} {shipping_info.get('last_name', '')}".strip()
    return f"""
        <div style="margin: 20px 0;">
            <p style="margin: 0 0 4px 0;"><strong>Shipping to:</strong></p>
            <p style="margin: 0; color: #9a9898;">
                {name}{f" &middot; {shipping_info['phone']}" if shipping_info.get('phone') else ""}<br>
                {shipping_info.get('address', '')}, {shipping_info.get('city', '')} {shipping_info.get('state', '')}
            </p>
        </div>
    """


def _render_product_details_html(
    name: str, price: Optional[float], description: str, image_url: Optional[str]
) -> str:
    image_html = ""
    if image_url:
        image_html = f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="{image_url}" alt="{html_lib.escape(name)}" style="max-width: 100%; width: 280px; border-radius: 8px; border: 1px solid #353534;">
        </div>
        """
    price_html = (
        f'<p style="margin: 4px 0 0 0; color: #ff6b00; font-weight: 700; font-size: 18px;">₦{price:,.2f}</p>'
        if price is not None
        else ""
    )
    description_html = (
        f'<p style="margin: 8px 0 0 0; color: #9a9898;">{html_lib.escape(description)}</p>'
        if description
        else ""
    )
    return f"""
        <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 20px; border-radius: 6px; margin: 20px 0;">
            {image_html}
            <p style="margin: 0; color: #ffffff; font-size: 18px; font-weight: 700;">{html_lib.escape(name)}</p>
            {price_html}
            {description_html}
        </div>
    """


async def send_verification_email(to_email: str, token: str):
    verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
    content = f"""
        <p>Welcome to ORON Watch Marketplace!</p>
        <p>Please verify your email address to unlock all features, including the ability to place active orders.</p>
        <div style="text-align: center;">
            <a href="{verify_url}" class="button">Verify My Email</a>
        </div>
        <p style="margin-top: 32px; font-size: 14px; color: #9a9898;">
            Or copy and paste this link into your browser:<br>
            <a href="{verify_url}" style="color: #ff6b00;">{verify_url}</a>
        </p>
    """
    html_template = get_base_html_template(
        title="Verify Your Email",
        preheader="Confirm your email address to finish setting up your ORON account.",
        content=content,
    )
    await send_email(to_email, "Welcome to ORON! Please verify your email.", html_template)


async def send_verify_and_set_password_email(to_email: str, token: str):
    set_password_url = f"{settings.FRONTEND_URL}/auth/set-password?token={token}"
    content = f"""
        <p>Welcome to ORON Watch Marketplace!</p>
        <p>We've received your order and are holding it for you. You're one step from tracking it: verify your email and set a password to access your order.</p>
        <div style="text-align: center;">
            <a href="{set_password_url}" class="button">Set My Password</a>
        </div>
        <p style="margin-top: 32px; font-size: 14px; color: #9a9898;">
            Or copy and paste this link into your browser:<br>
            <a href="{set_password_url}" style="color: #ff6b00;">{set_password_url}</a>
        </p>
    """
    html_template = get_base_html_template(
        title="Verify Your Email & Set a Password",
        preheader="You're one step from tracking your ORON order.",
        content=content,
    )
    await send_email(
        to_email,
        "Welcome to ORON! Set a password to continue your order.",
        html_template,
    )


async def send_account_access_email(to_email: str, token: str):
    set_password_url = f"{settings.FRONTEND_URL}/auth/set-password?token={token}"
    content = f"""
        <p>We received a request to access your ORON account.</p>
        <p>Click the button below to set a password and get in. If you didn't request this, you can safely ignore this email — your account is unchanged.</p>
        <div style="text-align: center;">
            <a href="{set_password_url}" class="button">Set My Password</a>
        </div>
        <p style="margin-top: 32px; font-size: 14px; color: #9a9898;">
            Or copy and paste this link into your browser:<br>
            <a href="{set_password_url}" style="color: #ff6b00;">{set_password_url}</a>
        </p>
        <p style="margin-top: 24px; font-size: 13px; color: #9a9898;">This link expires in 48 hours.</p>
    """
    html_template = get_base_html_template(
        title="Access Your ORON Account",
        preheader="Set a password to sign in to your ORON account.",
        content=content,
    )
    await send_email(to_email, "Access your ORON account", html_template)


async def send_bank_transfer_details_email(
    to_email: str,
    order_id: str,
    bank_name: str,
    account_number: str,
    account_name: str,
    amount: float,
    expires_at,
    order_url: Optional[str] = None,
    items: Optional[list] = None,
    shipping_info=None,
    created_at=None,
):
    order_ref = order_id[-6:]
    expires_str = (
        expires_at.strftime("%d %b %Y, %I:%M %p %Z") if expires_at else "shortly"
    )
    amount_str = f"₦{amount:,.2f}"
    order_url = order_url or f"{settings.FRONTEND_URL}/orders/{order_id}"
    date_str = created_at.strftime("%d %b %Y") if created_at else None
    content = f"""
        <p>Complete your payment for order #{order_ref}{f" (placed {date_str})" if date_str else ""} by making a bank transfer for the exact amount below to the dedicated account number provided.</p>
        <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
            <p><strong>Bank:</strong> {bank_name or 'N/A'}</p>
            <p><strong>Account Number:</strong> {account_number or 'N/A'}</p>
            <p><strong>Account Name:</strong> {account_name or 'N/A'}</p>
            <p><strong>Amount:</strong> {amount_str}</p>
        </div>
        <p>This account number is valid until <strong>{expires_str}</strong>. Transfer the exact amount shown — your order will be marked paid automatically once we receive it.</p>
        {f'<p style="margin-top: 24px;"><strong>Order Summary</strong></p>{_render_order_items_html(items)}' if items else ""}
        {_render_shipping_html(shipping_info)}
        <div style="text-align: center;">
            <a href="{order_url}" class="button">View Order</a>
        </div>
    """
    html_template = get_base_html_template(
        title="Complete Your Payment via Bank Transfer",
        preheader=f"Your dedicated account details for order #{order_ref}",
        content=content,
    )
    await send_email(to_email, "Complete Your Payment via Bank Transfer", html_template)


async def send_bank_transfer_expired_email(
    to_email: str, order_id: str, order_url: Optional[str] = None
):
    order_ref = order_id[-6:]
    order_url = order_url or f"{settings.FRONTEND_URL}/orders/{order_id}"
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
        content=content,
    )
    await send_email(to_email, f"Payment Window Expired: Order #{order_ref}", html_template)


async def send_payment_confirmation_email(
    to_email: str,
    order_id: str,
    amount: float,
    order_url: Optional[str] = None,
    items: Optional[list] = None,
    shipping_info=None,
    created_at=None,
):
    order_ref = order_id[-6:]
    amount_str = f"₦{amount:,.2f}"
    order_url = order_url or f"{settings.FRONTEND_URL}/orders/{order_id}"
    date_str = created_at.strftime("%d %b %Y") if created_at else None
    content = f"""
        <p>We've received your payment for order #{order_ref}{f" (placed {date_str})" if date_str else ""}. Thank you for shopping with ORON!</p>
        <div style="background-color: rgba(74,222,128,0.08); padding: 15px; border-radius: 6px; margin: 20px 0; border: 1px solid rgba(74,222,128,0.3);">
            <p style="margin: 0; color: #4ade80;"><strong>Amount Paid:</strong> {amount_str}</p>
        </div>
        {f'<p style="margin-top: 24px;"><strong>Order Summary</strong></p>{_render_order_items_html(items)}' if items else ""}
        {_render_shipping_html(shipping_info)}
        <p>We're now preparing your order. You'll get another email as its status changes.</p>
        <div style="text-align: center;">
            <a href="{order_url}" class="button">View Order</a>
        </div>
    """
    html_template = get_base_html_template(
        title="Payment Received",
        preheader=f"We've received your payment for order #{order_ref}.",
        content=content,
    )
    await send_email(to_email, f"Payment Confirmed: Order #{order_ref}", html_template)


async def send_notification_email(to_email: str, title: str, message: str):
    content = f"<p>{message}</p>"
    html_template = get_base_html_template(
        title=title, preheader=title, content=content
    )
    await send_email(to_email, title, html_template)


async def send_support_ticket_email(
    to_email: str, ticket_id: str, subject: str, message: str, is_admin: bool = False
):
    if is_admin:
        title = f"New Support Ticket: {subject}"
        content = f"""
            <p>A new support ticket has been created:</p>
            <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
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
            <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
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
        title=title, preheader=title, content=content
    )
    await send_email(to_email, title, html_template)


async def send_support_reply_email(
    to_email: str,
    ticket_id: str,
    subject: str,
    reply_message: str,
    sender_name: str,
    is_admin: bool = False,
):
    if is_admin:
        title = f"New Reply to Your Support Ticket: {subject}"
        content = f"""
            <p>You have received a reply to your support ticket from our team:</p>
            <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
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
            <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
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
        title=title, preheader=title, content=content
    )
    await send_email(to_email, title, html_template)


async def send_dispute_email(
    to_email: str,
    dispute_id: str,
    order_id: str,
    reason: str,
    description: str,
    is_admin: bool = False,
):
    if is_admin:
        title = f"New Dispute Filed: Order #{order_id[-6:]}"
        content = f"""
            <p>A new dispute has been filed for an order:</p>
            <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
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
            <div style="background-color: #1c1b1b; border: 1px solid #353534; padding: 15px; border-radius: 6px; margin: 20px 0;">
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
        title=title, preheader=title, content=content
    )
    await send_email(to_email, title, html_template)


async def send_announcement_message(
    to_email: str,
    subject: str,
    title: str,
    message: str,
    is_html: bool = False,
    unsubscribe_url: Optional[str] = None,
):
    """Send a short announcement email.

    - If `is_html` is False the `message` will be HTML-escaped and line breaks preserved.
    - `unsubscribe_url` if provided will be appended as a small unsubscribe link.
    """
    if not is_html:
        safe_message = html_lib.escape(message).replace("\n", "<br>")
    else:
        safe_message = message

    # Wrap in a paragraph if it doesn't look like full HTML
    content = (
        safe_message
        if ("<" in safe_message and ">" in safe_message)
        else f"<p>{safe_message}</p>"
    )

    if unsubscribe_url:
        content += f"""
        <p style=\"font-size:12px; color:#9a9898; margin-top:24px; text-align:center;\">
            <a href=\"{unsubscribe_url}\" style=\"color:#9a9898; text-decoration:underline;\">Unsubscribe</a>
        </p>
        """

    html_template = get_base_html_template(
        title=title, preheader=title, content=content
    )
    await send_email(to_email, subject, html_template)


async def send_new_product_email(
    to_email: str,
    product_id: str,
    name: str,
    description: str,
    price: float,
    image_url: Optional[str] = None,
    unsubscribe_url: Optional[str] = None,
):
    """Announce a newly-created product, with its picture and details, to a
    customer or newsletter subscriber."""
    product_url = f"{settings.FRONTEND_URL}/products/{product_id}"
    content = f"""
        <p>Check out our newest addition to the ORON collection:</p>
        {_render_product_details_html(name, price, description, image_url)}
        <div style="text-align: center;">
            <a href="{product_url}" class="button">View Product</a>
        </div>
    """

    if unsubscribe_url:
        content += f"""
        <p style=\"font-size:12px; color:#9a9898; margin-top:24px; text-align:center;\">
            <a href=\"{unsubscribe_url}\" style=\"color:#9a9898; text-decoration:underline;\">Unsubscribe</a>
        </p>
        """

    html_template = get_base_html_template(
        title="New Product Available",
        preheader=f"Check out {name}, now available at ORON.",
        content=content,
    )
    await send_email(to_email, f"New Arrival: {name}", html_template)
