from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import GlobalSettings
from modules import db
from modules.discord_handler import DiscordWebhookHandler
from . import admin2_bp

@admin2_bp.route('/admin/discord_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def discord_settings():
    settings = GlobalSettings.query.first()
    
    if request.method == 'POST':
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        settings.discord_webhook_url = request.form.get('discord_webhook_url', '')
        settings.discord_bot_name = request.form.get('discord_bot_name', '')
        settings.discord_bot_avatar_url = request.form.get('discord_bot_avatar_url', '')
        
        try:
            db.session.commit()
            flash('Discord settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating Discord settings: {str(e)}', 'error')
        
        return redirect(url_for('admin2.discord_settings'))

    # Set default values if no settings exist
    webhook_url = settings.discord_webhook_url if settings else 'insert_webhook_url_here'
    bot_name = settings.discord_bot_name if settings else 'SharewareZ Bot'
    bot_avatar_url = settings.discord_bot_avatar_url if settings else 'insert_bot_avatar_url_here'

    return render_template('admin/admin_manage_discord_settings.html',
                         webhook_url=webhook_url,
                         bot_name=bot_name,
                         bot_avatar_url=bot_avatar_url)

@admin2_bp.route('/admin/test_discord_webhook', methods=['POST'])
@login_required
@admin_required
def test_discord_webhook():
    data = request.json
    webhook_url = data.get('webhook_url')
    bot_name = data.get('bot_name')
    bot_avatar_url = data.get('bot_avatar_url')

    if not webhook_url:
        return jsonify({'success': False, 'message': 'Webhook URL is required'}), 400

    handler = DiscordWebhookHandler(webhook_url, bot_name, bot_avatar_url)
    
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
