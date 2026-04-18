# crminaec/core/email.py
from flask import current_app
from flask_mail import Message
from crminaec import mail

# Assuming you initialize 'mail' in your main __init__.py alongside 'db'
# If your mail object is initialized differently, adjust this import!



def send_confirmation_email(to_email, confirm_url):
    """Sends the registration confirmation email using Flask-Mail."""
    
    msg = Message(
        subject="EMEK Architecture Arkhon Portal - Hesabınızı Onaylayın",
        recipients=[to_email]
    )
    
    # Fallback plain text version
    msg.body = f"Arkhon portalına hoş geldiniz! Hesabınızı onaylamak için şu linke tıklayın: {confirm_url}"
    
    # Professional HTML version
    msg.html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #333; text-align: center;">Arkhon Portalına Hoş Geldiniz</h2>
        <p style="color: #555; font-size: 16px;">Hesabınızı başarıyla oluşturduk. Sisteme giriş yapabilmek için lütfen aşağıdaki butona tıklayarak e-posta adresinizi onaylayın.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{confirm_url}" style="background-color: #0d6efd; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">Hesabımı Onayla</a>
        </div>
        <p style="font-size: 12px; color: #777;">Eğer butona tıklayamıyorsanız, şu linki tarayıcınıza kopyalayıp yapıştırın:<br><a href="{confirm_url}">{confirm_url}</a></p>
        <hr style="border: none; border-top: 1px solid #eee; margin-top: 30px;">
        <p style="font-size: 12px; color: #999; text-align: center;">EMEK Architecture &copy; {current_app.config.get('CURRENT_YEAR', '2026')}</p>
    </div>
    """
    
    try:
        mail.send(msg)
        current_app.logger.info(f"✅ Confirmation email successfully sent to {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"❌ Failed to send email to {to_email}: {e}")
        return False