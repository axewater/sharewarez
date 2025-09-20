# /modules/routes_admin_ext/images.py
from flask import render_template, request, jsonify, current_app
from flask_login import login_required
from modules.models import Image, Game
from modules import db
from . import admin2_bp
from modules.utils_auth import admin_required
from sqlalchemy import select, func, delete

@admin2_bp.route('/admin/image_queue')
@login_required
@admin_required
def image_queue():
    """Display the image queue management interface."""
    return render_template('admin/admin_manage_image_queue.html')


@admin2_bp.route('/admin/api/image_queue_list')
@login_required
@admin_required
def image_queue_list():
    """Get paginated list of images in queue."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status', 'all')  # all, pending, downloaded
    type_filter = request.args.get('type', 'all')  # all, cover, screenshot
    
    query = select(Image).join(Game)
    
    # Apply filters
    if status_filter == 'pending':
        query = query.filter(Image.is_downloaded == False)
    elif status_filter == 'downloaded':
        query = query.filter(Image.is_downloaded == True)
    
    if type_filter != 'all':
        query = query.filter(Image.image_type == type_filter)
    
    # Order by creation date, pending first
    query = query.order_by(Image.is_downloaded.asc(), Image.created_at.desc())
    
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    images = pagination.items
    
    image_list = []
    for img in images:
        image_list.append({
            'id': img.id,
            'game_uuid': img.game_uuid,
            'game_name': img.game.name if img.game else 'Unknown',
            'image_type': img.image_type,
            'download_url': img.download_url,
            'is_downloaded': img.is_downloaded,
            'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'local_url': img.url if img.is_downloaded else None
        })
    
    return jsonify({
        'images': image_list,
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@admin2_bp.route('/admin/api/download_images', methods=['POST'])
@login_required
@admin_required
def download_images():
    """Download specific images or batch download."""
    data = request.json

    try:
        if 'image_ids' in data:
            # Download specific images
            image_ids = data['image_ids']
            downloaded = 0

            for image_id in image_ids:
                image = db.session.get(Image, image_id)
                if image and not image.is_downloaded and image.download_url:
                    try:
                        import os
                        from modules.utils_functions import download_image
                        save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
                        download_image(image.download_url, save_path)
                        image.is_downloaded = True
                        downloaded += 1
                    except Exception as e:
                        print(f"Failed to download image {image_id}: {e}")

            db.session.commit()
            return jsonify({
                'success': True,
                'downloaded': downloaded,
                'message': f'Downloaded {downloaded} images'
            })

        elif 'batch_size' in data:
            # Batch download
            from modules.utils_game_core import download_pending_images
            batch_size = data.get('batch_size', 10)
            downloaded = download_pending_images(batch_size=batch_size, delay_between_downloads=0.1, app=current_app)

            return jsonify({
                'success': True,
                'downloaded': downloaded,
                'message': f'Downloaded {downloaded} images'
            })

        else:
            return jsonify({'success': False, 'message': 'No valid parameters provided'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin2_bp.route('/admin/api/delete_image/<int:image_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_image(image_id):
    """Delete a specific image from queue."""
    try:
        image = db.session.get(Image, image_id)
        if not image:
            return jsonify({'success': False, 'message': 'Image not found'}), 404
        
        # Delete file if it exists
        if image.is_downloaded and image.url:
            import os
            file_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(image)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Image deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


