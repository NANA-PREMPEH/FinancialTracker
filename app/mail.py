from flask_mail import Mail, Message
from flask import render_template, current_app

mail = Mail()


def send_verification_email(user, token):
    try:
        msg = Message(
            'Verify your FinTracker account',
            recipients=[user.email]
        )
        msg.html = render_template('email/verify.html', user=user, token=token)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send verification email: {e}')
        return False


def send_reset_email(user, token):
    try:
        msg = Message(
            'Reset your FinTracker password',
            recipients=[user.email]
        )
        msg.html = render_template('email/reset.html', user=user, token=token)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send reset email: {e}')
        return False
