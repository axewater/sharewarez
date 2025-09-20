from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.forms import ThemeUploadForm
from modules.utils_themes import ThemeManager
from modules.utils_logging import log_system_event
import os
import shutil
from pathlib import Path
from typing import Optional, Union
from . import admin2_bp

# Configuration constants
MAX_THEME_FILE_SIZE = 25 * 1024 * 1024  # 25MB in bytes
ZIP_MAGIC_BYTES = [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08']  # Standard ZIP file signatures
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}

def validate_theme_file(file) -> tuple[bool, Optional[str]]:
    """Validate uploaded theme file for security and format requirements.
    
    Args:
        file: Uploaded file object from form
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not file or not file.filename:
        return False, "No file provided"
    
    # Check file size
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > MAX_THEME_FILE_SIZE:
        return False, f"File size ({file_size / (1024*1024):.1f}MB) exceeds maximum allowed size (25MB)"
    
    if file_size == 0:
        return False, "File is empty"
    
    # Check magic bytes for ZIP file
    file_header = file.read(4)
    file.seek(0)  # Reset to beginning
    
    if not any(file_header.startswith(magic) for magic in ZIP_MAGIC_BYTES):
        return False, "File is not a valid ZIP archive"
    
    return True, None


def is_valid_theme_name(name: str) -> tuple[bool, Optional[str]]:
    """Check if theme name is valid and safe to use.
    
    Args:
        name: Theme name to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Theme name cannot be empty"
    
    # Check for Windows reserved names
    name_upper = name.upper()
    if name_upper in WINDOWS_RESERVED_NAMES:
        return False, f"'{name}' is a reserved system name and cannot be used"
    
    # Check for reserved names with extensions
    if '.' in name_upper:
        base_name = name_upper.split('.')[0]
        if base_name in WINDOWS_RESERVED_NAMES:
            return False, f"'{name}' uses a reserved system name and cannot be used"
    
    # Check for dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    if any(char in name for char in dangerous_chars):
        return False, f"Theme name contains invalid characters: {', '.join(char for char in dangerous_chars if char in name)}"
    
    # Check for path traversal attempts  
    if '..' in name or (name.startswith('.') and name != '.') or name.endswith('.'):
        return False, "Theme name contains invalid path elements"
    
    return True, None


@admin2_bp.route('/admin/themes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_themes():
    """Manage themes - upload, list, and configure themes.
    
    Returns:
        Response: Rendered template or redirect
    """
    form = ThemeUploadForm()
    theme_manager = ThemeManager(current_app)
    upload_folder = Path(current_app.config['UPLOAD_FOLDER']) / 'themes'
    
    if not upload_folder.exists():
        try:
            upload_folder.mkdir(parents=True, exist_ok=True)
            log_system_event(
                f"Created themes upload directory: {upload_folder}",
                event_type='themes',
                event_level='information'
            )
        except Exception as e:
            log_system_event(
                f"Error creating upload directory: {e}",
                event_type='themes',
                event_level='error'
            )
            flash("Error processing request. Please try again.", 'error')
            return redirect(url_for('admin2.manage_themes'))

    if form.validate_on_submit():
        theme_zip = form.theme_zip.data
        
        # Validate the uploaded file
        is_valid_file, file_error = validate_theme_file(theme_zip)
        if not is_valid_file:
            log_system_event(
                f"Theme upload failed - file validation: {file_error}",
                event_type='themes',
                event_level='warning'
            )
            flash(f"Upload failed: {file_error}", 'error')
            return redirect(url_for('admin2.manage_themes'))
        
        try:
            theme_data = theme_manager.upload_theme(theme_zip)
            if theme_data:
                # Validate theme name
                is_valid_name, name_error = is_valid_theme_name(theme_data.get('name', ''))
                if not is_valid_name:
                    log_system_event(
                        f"Theme upload failed - invalid name '{theme_data.get('name', '')}': {name_error}",
                        event_type='themes',
                        event_level='warning'
                    )
                    flash(f"Upload failed: {name_error}", 'error')
                    return redirect(url_for('admin2.manage_themes'))
                
                log_system_event(
                    f"Theme '{theme_data['name']}' uploaded successfully by admin",
                    event_type='themes',
                    event_level='information'
                )
                flash(f"Theme '{theme_data['name']}' uploaded successfully!", 'success')
            else:
                log_system_event(
                    "Theme upload failed - no theme data returned",
                    event_type='themes',
                    event_level='error'
                )
                flash("Theme upload failed. Please check the error messages.", 'error')
        except ValueError as e:
            log_system_event(
                f"Theme upload failed with ValueError: {e}",
                event_type='themes',
                event_level='warning'
            )
            flash(str(e), 'error')
        except Exception as e:
            log_system_event(
                f"Theme upload failed with unexpected error: {e}",
                event_type='themes',
                event_level='error'
            )
            flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('admin2.manage_themes'))

    installed_themes = theme_manager.get_installed_themes()
    default_theme = theme_manager.get_default_theme()
    return render_template('admin/admin_manage_themes.html', form=form, themes=installed_themes, default_theme=default_theme)

@admin2_bp.route('/admin/themes/readme')
@login_required
@admin_required
def theme_readme():
    """Display theme documentation and readme information.
    
    Returns:
        Response: Rendered template with theme documentation
    """
    return render_template('admin/admin_manage_themes_readme.html')

@admin2_bp.route('/admin/themes/delete/<theme_name>', methods=['POST'])
@login_required
@admin_required
def delete_theme(theme_name: str):
    """Delete a theme from the system.
    
    Args:
        theme_name: Name of the theme to delete
        
    Returns:
        Response: Redirect to themes management page
    """
    theme_manager = ThemeManager(current_app)
    
    # Validate theme name before deletion
    is_valid_name, name_error = is_valid_theme_name(theme_name)
    if not is_valid_name:
        log_system_event(
            f"Theme deletion failed - invalid name '{theme_name}': {name_error}",
            event_type='themes',
            event_level='warning'
        )
        flash(f"Deletion failed: {name_error}", 'error')
        return redirect(url_for('admin2.manage_themes'))
    
    try:
        theme_manager.delete_themefile(theme_name)
        log_system_event(
            f"Theme '{theme_name}' deleted successfully by admin",
            event_type='themes',
            event_level='information'
        )
        flash(f"Theme '{theme_name}' deleted successfully!", 'success')
    except ValueError as e:
        log_system_event(
            f"Theme deletion failed with ValueError: {e}",
            event_type='themes',
            event_level='warning'
        )
        flash(str(e), 'error')
    except Exception as e:
        log_system_event(
            f"Theme deletion failed with unexpected error: {e}",
            event_type='themes',
            event_level='error'
        )
        flash(f"An unexpected error occurred: {str(e)}", 'error')
    return redirect(url_for('admin2.manage_themes'))

@admin2_bp.route('/admin/themes/reset', methods=['POST'])
@login_required
@admin_required
def reset_default_themes():
    """Reset themes to default by copying from source directory.

    Returns:
        Response: Redirect to themes management page
    """
    try:
        default_theme_source = Path('modules') / 'setup' / 'default_theme'
        if not default_theme_source.exists():
            error_msg = "Failed to reset default themes: source directory not found"
            flash('Error: default theme source not found in modules/setup/default_theme', 'error')
            log_system_event(
                error_msg,
                event_type='themes',
                event_level='error'
            )
            return redirect(url_for('admin2.manage_themes'))

        default_theme_target = Path('modules') / 'static' / 'library' / 'themes' / 'default'

        log_system_event(
            "Starting default themes reset...",
            event_type='themes',
            event_level='information'
        )

        # Remove existing default theme if it exists
        if default_theme_target.exists():
            try:
                shutil.rmtree(default_theme_target)
                log_system_event(
                    "Removed existing default theme directory",
                    event_type='themes',
                    event_level='information'
                )
            except Exception as e:
                error_message = f"Failed to remove existing default theme: {str(e)}"
                flash(error_message, 'error')
                log_system_event(error_message, event_type='themes', event_level='error')
                return redirect(url_for('admin2.manage_themes'))

        # Create themes directory if it doesn't exist
        default_theme_target.parent.mkdir(parents=True, exist_ok=True)

        # Copy default theme from source
        try:
            shutil.copytree(default_theme_source, default_theme_target)
            log_system_event(
                "Default theme copied successfully from source directory",
                event_type='themes',
                event_level='information'
            )
            flash('Default themes have been reset successfully!', 'success')
        except Exception as e:
            error_message = f"Failed to copy default theme: {str(e)}"
            flash(error_message, 'error')
            log_system_event(error_message, event_type='themes', event_level='error')

    except Exception as e:
        error_message = f"Error resetting default themes: {str(e)}"
        flash(error_message, 'error')
        log_system_event(error_message, event_type='themes', event_level='error')

    return redirect(url_for('admin2.manage_themes'))
