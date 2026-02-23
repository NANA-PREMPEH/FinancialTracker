from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from . import db
from .models import User, PasswordResetToken, EmailVerificationToken, SecurityEvent
from .mail import send_verification_email, send_reset_email
from datetime import datetime, timedelta
import secrets
import pyotp
import qrcode
import io
import base64

auth = Blueprint('auth', __name__, url_prefix='/auth')


def _log_security_event(user_id, event_type, details=None):
    event = SecurityEvent(
        user_id=user_id,
        event_type=event_type,
        ip_address=request.remote_addr,
        details=details
    )
    db.session.add(event)
    db.session.commit()


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # Check if 2FA is enabled
            if user.totp_enabled and user.totp_secret:
                session['2fa_user_id'] = user.id
                session['2fa_remember'] = bool(request.form.get('remember'))
                return redirect(url_for('auth.verify_2fa'))

            login_user(user, remember=request.form.get('remember'))
            user.last_login = datetime.utcnow()
            db.session.commit()
            _log_security_event(user.id, 'login_success')
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            if user:
                _log_security_event(user.id, 'login_failed', 'Invalid password')
            flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@auth.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    user_id = session.get('2fa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        totp_code = request.form.get('totp_code', '').strip()
        user = User.query.get(user_id)

        if user and user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(totp_code, valid_window=1):
                remember = session.pop('2fa_remember', False)
                session.pop('2fa_user_id', None)
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()
                _log_security_event(user.id, 'login_success', '2FA verified')
                flash('Welcome back!', 'success')
                return redirect(url_for('main.dashboard'))
            else:
                _log_security_event(user.id, 'login_failed', 'Invalid 2FA code')
                flash('Invalid authentication code. Please try again.', 'error')
        else:
            session.pop('2fa_user_id', None)
            return redirect(url_for('auth.login'))

    return render_template('auth/verify_2fa.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('auth/register.html')

        user = User(name=name, email=email)
        user.set_password(password)

        # First user becomes admin
        if User.query.count() == 0:
            user.role = 'admin'

        db.session.add(user)
        db.session.commit()

        # Send verification email
        token = secrets.token_urlsafe(48)
        verification = EmailVerificationToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.session.add(verification)
        db.session.commit()

        email_sent = send_verification_email(user, token)

        if email_sent:
            flash('Account created! Please check your email to verify your account.', 'success')
            return render_template('auth/verify_email.html', email=email)
        else:
            # If email fails, still log them in (graceful fallback)
            login_user(user)
            flash('Account created successfully! Email verification is pending.', 'success')
            return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html')


@auth.route('/verify/<token>')
def verify_email(token):
    verification = EmailVerificationToken.query.filter_by(token=token, used=False).first()

    if not verification:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('auth.login'))

    if verification.is_expired():
        flash('This verification link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.login'))

    verification.used = True
    verification.user.email_verified = True
    db.session.commit()

    _log_security_event(verification.user_id, 'email_verified')
    flash('Email verified successfully! You can now sign in.', 'success')
    return redirect(url_for('auth.login'))


@auth.route('/resend-verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()

    if user and not user.email_verified:
        # Invalidate old tokens
        EmailVerificationToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
        db.session.commit()

        token = secrets.token_urlsafe(48)
        verification = EmailVerificationToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.session.add(verification)
        db.session.commit()
        send_verification_email(user, token)

    # Always show success to prevent email enumeration
    flash('If an account exists with that email, a verification link has been sent.', 'success')
    return render_template('auth/verify_email.html', email=email)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


# --- Secure Password Reset Flow ---

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Request a password reset link via email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            # Invalidate any existing reset tokens
            PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
            db.session.commit()

            token = secrets.token_urlsafe(48)
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(reset_token)
            db.session.commit()

            send_reset_email(user, token)

        # Always show same message to prevent email enumeration
        flash('If an account exists with that email, a password reset link has been sent.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/request_reset.html')


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def reset_with_token(token):
    """Reset password using a secure token from email."""
    reset_token = PasswordResetToken.query.filter_by(token=token, used=False).first()

    if not reset_token or reset_token.is_expired():
        flash('This password reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.reset_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password:
            flash('Password is required.', 'error')
            return render_template('auth/reset_with_token.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_with_token.html')

        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('auth/reset_with_token.html')

        user = reset_token.user
        user.set_password(new_password)
        reset_token.used = True
        db.session.commit()

        _log_security_event(user.id, 'password_change', 'Password reset via email token')
        flash('Password updated successfully! Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_with_token.html')


# --- 2FA Setup ---

@auth.route('/setup-2fa')
@login_required
def setup_2fa():
    """Show QR code for TOTP 2FA setup."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name='FinTracker'
    )

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_b64 = base64.b64encode(buffer.getvalue()).decode()

    return render_template('auth/setup_2fa.html', qr_code=qr_code_b64, secret=secret)


@auth.route('/enable-2fa', methods=['POST'])
@login_required
def enable_2fa():
    """Verify TOTP code and enable 2FA for the user."""
    secret = request.form.get('secret', '')
    totp_code = request.form.get('totp_code', '').strip()

    if not secret or not totp_code:
        flash('Please enter the 6-digit code from your authenticator app.', 'error')
        return redirect(url_for('auth.setup_2fa'))

    totp = pyotp.TOTP(secret)
    if totp.verify(totp_code, valid_window=1):
        current_user.totp_secret = secret
        current_user.totp_enabled = True
        db.session.commit()
        _log_security_event(current_user.id, '2fa_enabled')
        flash('Two-factor authentication has been enabled successfully!', 'success')
        return redirect(url_for('security.security_dashboard'))
    else:
        flash('Invalid code. Please try again with the code from your authenticator app.', 'error')
        return redirect(url_for('auth.setup_2fa'))


@auth.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA for the current user."""
    password = request.form.get('password', '')

    if not current_user.check_password(password):
        flash('Incorrect password. 2FA was not disabled.', 'error')
        return redirect(url_for('security.security_dashboard'))

    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.session.commit()
    _log_security_event(current_user.id, '2fa_disabled')
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('security.security_dashboard'))


# --- OAuth / Social Login ---

@auth.route('/login/google')
def google_login():
    """Redirect to Google OAuth."""
    from .oauth import oauth
    google = oauth.create_client('google')
    if not google:
        flash('Google login is not configured.', 'error')
        return redirect(url_for('auth.login'))
    redirect_uri = url_for('auth.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@auth.route('/login/google/callback')
def google_callback():
    """Handle Google OAuth callback."""
    from .oauth import oauth
    google = oauth.create_client('google')
    if not google:
        flash('Google login is not configured.', 'error')
        return redirect(url_for('auth.login'))

    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            user_info = google.userinfo()
    except Exception as e:
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    email = user_info.get('email', '').lower()
    name = user_info.get('name', email.split('@')[0])
    google_id = user_info.get('sub')

    if not email:
        flash('Could not retrieve email from Google.', 'error')
        return redirect(url_for('auth.login'))

    # Find existing user by email or OAuth ID
    user = User.query.filter_by(email=email).first()

    if user:
        # Link OAuth if not already linked
        if not user.oauth_provider:
            user.oauth_provider = 'google'
            user.oauth_id = google_id
            user.email_verified = True
        db.session.commit()
    else:
        # Create new user
        user = User(
            name=name,
            email=email,
            oauth_provider='google',
            oauth_id=google_id,
            email_verified=True
        )
        user.set_password(secrets.token_urlsafe(32))  # Random password for OAuth users

        if User.query.count() == 0:
            user.role = 'admin'

        db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()
    _log_security_event(user.id, 'login_success', 'Google OAuth')
    flash('Welcome!', 'success')
    return redirect(url_for('main.dashboard'))
