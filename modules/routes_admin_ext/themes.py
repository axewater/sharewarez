from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.forms import ThemeUploadForm
from modules.utils_themes import ThemeManager
from modules.utils_logging import log_system_event
import os
import zipfile
from . import admin2_bp

@admin2_bp.route('/admin/themes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_themes():
    form = ThemeUploadForm()
    theme_manager = ThemeManager(current_app)
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'themes')
    if not os.path.exists(upload_folder):
        try:
            # Safe check to avoid creating 'static' directly
            os.makedirs(upload_folder, exist_ok=True)
        except Exception as e:
            print(f"Error creating upload directory: {e}")
            flash("Error processing request. Please try again.", 'error')
            return redirect(url_for('admin2.manage_themes'))

    if form.validate_on_submit():
        theme_zip = form.theme_zip.data
        try:
            theme_data = theme_manager.upload_theme(theme_zip)
            if theme_data:
                flash(f"Theme '{theme_data['name']}' uploaded successfully!", 'success')
            else:
                flash("Theme upload failed. Please check the error messages.", 'error')
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('admin2.manage_themes'))

    installed_themes = theme_manager.get_installed_themes()
    default_theme = theme_manager.get_default_theme()
    return render_template('admin/admin_manage_themes.html', form=form, themes=installed_themes, default_theme=default_theme)

@admin2_bp.route('/admin/themes/readme')
@login_required
@admin_required
def theme_readme():
    return render_template('admin/admin_manage_themes_readme.html')

@admin2_bp.route('/admin/themes/delete/<theme_name>', methods=['POST'])
@login_required
@admin_required
def delete_theme(theme_name):
    theme_manager = ThemeManager(current_app)
    try:
        theme_manager.delete_themefile(theme_name)
        flash(f"Theme '{theme_name}' deleted successfully!", 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
    return redirect(url_for('admin2.manage_themes'))

@admin2_bp.route('/admin/themes/reset', methods=['POST'])
@login_required
@admin_required
def reset_default_themes():
    try:
        themes_zip = os.path.join('modules', 'setup', 'themes.zip')
        if not os.path.exists(themes_zip):
            flash('Error: themes.zip not found in modules/setup/', 'error')
            log_system_event(
                "Failed to reset default themes: themes.zip not found",
                event_type='themes',
                event_level='error'
            )
            return redirect(url_for('admin2.manage_themes'))

        library_path = os.path.join('modules', 'static', 'library')
        log_details = []
        
        print("Starting default themes reset...")
        with zipfile.ZipFile(themes_zip, 'r') as zip_ref:
            files_list = zip_ref.namelist()
            print(f"Found {len(files_list)} files in themes.zip")
            
            for file in files_list:
                try:
                    zip_ref.extract(file, library_path)
                    log_message = f"Successfully extracted: {file}"
                    print(log_message)
                    log_details.append(log_message)
                except Exception as e:
                    error_message = f"Failed to extract {file}: {str(e)}"
                    print(error_message)
                    log_details.append(error_message)

        successful_extracts = len([log for log in log_details if log.startswith("Successfully")])
        failed_extracts = len([log for log in log_details if log.startswith("Failed")])
        
        summary = f"Default themes reset: {successful_extracts} files extracted successfully, {failed_extracts} failed"
        full_log = "\n".join(log_details)
        log_system_event(
            f"{summary}\nDetails:\n{full_log}",
            event_type='themes',
            event_level='information' if failed_extracts == 0 else 'warning'
        )

        if failed_extracts == 0:
            flash('Default themes have been reset successfully!', 'success')
        else:
            flash(f'Default themes reset completed with {failed_extracts} errors. Check system logs for details.', 'warning')

    except Exception as e:
        error_message = f"Error resetting default themes: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
        log_system_event(error_message, event_type='themes', event_level='error')

    return redirect(url_for('admin2.manage_themes'))
