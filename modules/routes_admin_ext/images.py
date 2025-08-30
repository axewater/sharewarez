# /modules/routes_admin_ext/images.py
from flask import render_template, request, jsonify, current_app
from flask_login import login_required
from modules.models import Image, Game
from modules import db
from . import admin2_bp
from modules.utils_auth import admin_required
from sqlalchemy import select, func

@admin2_bp.route('/admin/image_queue')
@login_required
@admin_required
def image_queue():
    """Display the image queue management interface."""
    return render_template('admin/admin_manage_image_queue.html')


@admin2_bp.route('/admin/api/image_queue_stats')
@login_required
@admin_required
def image_queue_stats():
    """Get statistics about the image queue."""
    try:
        total_images = db.session.execute(select(func.count(Image.id))).scalar()
        pending_images = db.session.execute(select(func.count(Image.id)).filter_by(is_downloaded=False)).scalar()
        downloaded_images = db.session.execute(select(func.count(Image.id)).filter_by(is_downloaded=True)).scalar()
        
        # Get breakdown by image type
        pending_covers = db.session.execute(select(func.count(Image.id)).filter_by(is_downloaded=False, image_type='cover')).scalar()
        pending_screenshots = db.session.execute(select(func.count(Image.id)).filter_by(is_downloaded=False, image_type='screenshot')).scalar()
        
        # Get recent activity
        recent_downloads = db.session.execute(select(Image).filter_by(is_downloaded=True).order_by(Image.created_at.desc()).limit(10)).scalars().all()
        
        stats = {
            'total_images': total_images,
            'pending_images': pending_images,
            'downloaded_images': downloaded_images,
            'pending_covers': pending_covers,
            'pending_screenshots': pending_screenshots,
            'download_percentage': round((downloaded_images / total_images * 100) if total_images > 0 else 0, 1),
            'recent_downloads': [
                {
                    'id': img.id,
                    'game_name': img.game.name if img.game else 'Unknown',
                    'image_type': img.image_type,
                    'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S')
                } for img in recent_downloads
            ]
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    """Trigger download of specific images or batch download."""
    data = request.json
    
    try:
        if 'image_ids' in data:
            # Download specific images
            from modules.utils_game_core import download_pending_images
            image_ids = data['image_ids']
            
            # Update the download function to accept specific IDs
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


@admin2_bp.route('/admin/api/retry_failed_images', methods=['POST'])
@login_required
@admin_required
def retry_failed_images():
    """Retry downloading images that failed."""
    try:
        # Find images that should be downloaded but aren't
        failed_images = db.session.execute(select(Image).filter_by(is_downloaded=False).filter(Image.download_url.isnot(None))).scalars().all()
        
        retried = 0
        for image in failed_images:
            try:
                import os
                from modules.utils_functions import download_image
                save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
                download_image(image.download_url, save_path)
                image.is_downloaded = True
                retried += 1
            except Exception as e:
                print(f"Retry failed for image {image.id}: {e}")
                continue
        
        db.session.commit()
        return jsonify({
            'success': True,
            'retried': retried,
            'message': f'Retried {retried} failed images'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin2_bp.route('/admin/api/clear_downloaded_queue', methods=['POST'])
@login_required
@admin_required
def clear_downloaded_queue():
    """Remove all downloaded images from the queue view."""
    try:
        downloaded_count = db.session.execute(select(func.count(Image.id)).filter_by(is_downloaded=True)).scalar()
        # Note: We don't actually delete them, just for display purposes
        # If you want to actually delete downloaded records, uncomment below:
        # Image.query.filter_by(is_downloaded=True).delete()
        # db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{downloaded_count} downloaded images cleared from view'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin2_bp.route('/admin/api/start_background_downloader', methods=['POST'])
@login_required
@admin_required
def start_background_downloader():
    """Start the background image downloader."""
    try:
        from modules.utils_game_core import start_background_image_downloader
        thread = start_background_image_downloader(interval_seconds=60)
        
        return jsonify({
            'success': True,
            'message': 'Background image downloader started successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin2_bp.route('/admin/api/turbo_download', methods=['POST'])
@login_required
@admin_required
def turbo_download():
    """TURBO MODE: Maximum speed parallel downloading with 5 threads."""
    try:
        data = request.json or {}
        batch_size = data.get('batch_size', 100)
        max_workers = data.get('max_workers', 5)
        
        from modules.utils_game_core import turbo_download_images
        result = turbo_download_images(batch_size=batch_size, max_workers=max_workers, app=current_app)
        
        return jsonify({
            'success': True,
            'downloaded': result['downloaded'],
            'failed': result['failed'],
            'message': result['message']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin2_bp.route('/admin/api/start_turbo_downloader', methods=['POST'])
@login_required
@admin_required
def start_turbo_downloader():
    """Start the TURBO background downloader with parallel processing."""
    try:
        data = request.json or {}
        max_workers = data.get('max_workers', 4)
        batch_size = data.get('batch_size', 50)
        interval = data.get('interval', 30)
        
        from modules.utils_game_core import start_turbo_background_downloader
        thread = start_turbo_background_downloader(
            interval_seconds=interval, 
            max_workers=max_workers, 
            batch_size=batch_size
        )
        
        return jsonify({
            'success': True,
            'message': f'TURBO background downloader started! {max_workers} workers, {batch_size} batch size, {interval}s interval'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
