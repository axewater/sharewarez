from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import GlobalSettings
from modules import db
from sqlalchemy import select
from modules.discord_handler import DiscordWebhookHandler
from modules.utils_functions import validate_discord_webhook_url, validate_discord_bot_name, validate_discord_avatar_url
from . import admin2_bp

@admin2_bp.route('/admin/discord_help')
@login_required
@admin_required
def discord_help():
    return render_template('admin/admin_manage_discord_readme.html')

@admin2_bp.route('/admin/discord_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def discord_settings():
    settings = db.session.execute(select(GlobalSettings)).scalars().first()
    
    if request.method == 'POST':
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        # Get form data
        webhook_url_input = request.form.get('discord_webhook_url', '').strip()
        bot_name_input = request.form.get('discord_bot_name', '').strip()
        avatar_url_input = request.form.get('discord_bot_avatar_url', '').strip()
        
        # Validate inputs
        webhook_valid, webhook_result = validate_discord_webhook_url(webhook_url_input)
        bot_name_valid, bot_name_result = validate_discord_bot_name(bot_name_input)
        avatar_valid, avatar_result = validate_discord_avatar_url(avatar_url_input)
        
        # Check for validation errors
        if not webhook_valid:
            flash(f'Webhook URL error: {webhook_result}', 'error')
            return redirect(url_for('admin2.discord_settings'))
        
        if not bot_name_valid:
            flash(f'Bot name error: {bot_name_result}', 'error')
            return redirect(url_for('admin2.discord_settings'))
            
        if not avatar_valid:
            flash(f'Avatar URL error: {avatar_result}', 'error')
            return redirect(url_for('admin2.discord_settings'))
        
        # If validation passes, update settings with sanitized values
        settings.discord_webhook_url = webhook_result
        settings.discord_bot_name = bot_name_result
        settings.discord_bot_avatar_url = avatar_result
        
        try:
            db.session.commit()
            flash('Discord settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating Discord settings: {str(e)}', 'error')
        
        return redirect(url_for('admin2.discord_settings'))

    # Set default values if no settings exist or if fields are None
    webhook_url = (settings.discord_webhook_url if settings and settings.discord_webhook_url else 'insert_webhook_url_here')
    bot_name = (settings.discord_bot_name if settings and settings.discord_bot_name else 'SharewareZ Bot')
    bot_avatar_url = (settings.discord_bot_avatar_url if settings and settings.discord_bot_avatar_url else 'insert_bot_avatar_url_here')

    return render_template('admin/admin_manage_discord_settings.html',
                         webhook_url=webhook_url,
                         bot_name=bot_name,
                         bot_avatar_url=bot_avatar_url)

@admin2_bp.route('/admin/test_discord_webhook', methods=['POST'])
@login_required
@admin_required
def test_discord_webhook():
    data = request.json
    webhook_url_input = data.get('webhook_url', '').strip()
    bot_name_input = data.get('bot_name', '').strip()
    bot_avatar_url_input = data.get('bot_avatar_url', '').strip()

    # Validate inputs
    webhook_valid, webhook_result = validate_discord_webhook_url(webhook_url_input)
    if not webhook_valid:
        return jsonify({'success': False, 'message': f'Webhook URL error: {webhook_result}'}), 400
    
    bot_name_valid, bot_name_result = validate_discord_bot_name(bot_name_input)
    if not bot_name_valid:
        return jsonify({'success': False, 'message': f'Bot name error: {bot_name_result}'}), 400
    
    avatar_valid, avatar_result = validate_discord_avatar_url(bot_avatar_url_input)
    if not avatar_valid:
        return jsonify({'success': False, 'message': f'Avatar URL error: {avatar_result}'}), 400

    # Use sanitized values
    handler = DiscordWebhookHandler(webhook_result, bot_name_result, avatar_result)
    
    try:
        embed = handler.create_embed(
            title="Discord Webhook Test",
            description="This is a test message from your SharewareZ instance.",
            color="03b2f8"
        )
        success = handler.send_webhook(embed)
        if success:
            return jsonify({'success': True, 'message': 'Test message sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send test message'}), 500
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        error_message = f"Discord webhook error: {str(e)}"
        print(error_message)
        return jsonify({'success': False, 'message': error_message}), 500
