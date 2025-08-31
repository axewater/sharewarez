# /modules/routes_admin_ext/newsletter.py
from flask import render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from flask_mail import Message as MailMessage
from modules.models import User, Newsletter, GlobalSettings
from modules import db, mail
from sqlalchemy import select
from modules.forms import NewsletterForm
from . import admin2_bp
from modules.utils_auth import admin_required

@admin2_bp.route('/admin/newsletter', methods=['GET', 'POST'])
@login_required
@admin_required
def newsletter():
    settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
    # Check if SMTP is configured and enabled
    if not settings_record or not settings_record.smtp_enabled:
        flash('SMTP is not configured or enabled. Please configure SMTP settings first.', 'warning')
        return redirect(url_for('site.admin_dashboard'))

    # Check if newsletter feature is enabled
    enable_newsletter = settings_record.settings.get('enableNewsletterFeature', False) if settings_record else False

    if not enable_newsletter:
        flash('Newsletter feature is disabled.', 'warning')
        return redirect(url_for('site.admin_dashboard'))

    # Verify SMTP sender is configured
    if not settings_record.smtp_default_sender:
        flash('SMTP default sender email is not configured.', 'warning')
        return redirect(url_for('site.admin_dashboard'))

    print("ADMIN NEWSLETTER: Processing", request.method, "request")
    form = NewsletterForm()
    users = db.session.execute(select(User)).scalars().all()
    if form.validate_on_submit():
        # First create the newsletter record
        recipients = form.recipients.data.split(',')        
        new_newsletter = Newsletter(
            subject=form.subject.data,
            content=form.content.data,
            sender_id=current_user.id,
            recipient_count=len(recipients),
            recipients=recipients,
            status='pending'
        )
        db.session.add(new_newsletter)
        db.session.commit()

        try:
            # Attempt to send the email
            msg = MailMessage(form.subject.data, sender=settings_record.smtp_default_sender)
            msg.html = form.content.data
            msg.recipients = recipients
            
            mail.send(msg)
            
            # Update status to sent
            new_newsletter.status = 'sent'
            db.session.commit()
            flash('Newsletter sent successfully!', 'success')
        except Exception as e:
            new_newsletter.status = 'failed'
            new_newsletter.error_message = str(e)
            db.session.commit()
            flash(str(e), 'error')
        return redirect(url_for('admin2.newsletter'))
    
    # Get all sent newsletters for display
    newsletters = db.session.execute(select(Newsletter).order_by(Newsletter.sent_date.desc())).scalars().all()
    return render_template('admin/admin_newsletter.html', 
                         title='Newsletter', 
                         form=form, 
                         users=users,
                         newsletters=newsletters)

@admin2_bp.route('/admin/newsletter/<int:newsletter_id>')
@login_required
@admin_required
def view_newsletter(newsletter_id):
    newsletter = db.session.get(Newsletter, newsletter_id) or abort(404)
    return render_template('admin/view_newsletter.html', 
                         title='View Newsletter',
                         newsletter=newsletter)
