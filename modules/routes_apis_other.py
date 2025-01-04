import os
from flask import Blueprint, jsonify, current_app
from modules.utils_processors import get_global_settings
from modules import cache, db
from flask_login import login_required, current_user
from modules.utils_auth import admin_required
from modules.utils_igdb_api import make_igdb_api_request, get_cover_thumbnail_url
from modules.utils_game_core import check_existing_game_by_igdb_id
from modules.utils_functions import PLATFORM_IDS
from modules.models import Library, Image, Game, User, AllowedFileType, IgnoredFileType, ScanJob, UnmatchedFolder, DownloadRequest
from sqlalchemy.exc import IntegrityError
from flask import request, url_for
from sqlalchemy import func
apis_other_bp = Blueprint('apis_other', __name__)

@apis_other_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@apis_other_bp.route('/api/scan_jobs_status', methods=['GET'])
@login_required
@admin_required
def scan_jobs_status():
    jobs = ScanJob.query.all()
    jobs_data = [{
        'id': job.id,
        'library_name': job.library.name if job.library else 'No Library Assigned',
        'folders': job.folders,
        'status': job.status,
        'total_folders': job.total_folders,
        'folders_success': job.folders_success,
        'folders_failed': job.folders_failed,
        'removed_count': job.removed_count,
        'scan_folder': job.scan_folder,
        'setting_remove': bool(job.setting_remove),
        'error_message': job.error_message,
        'last_run': job.last_run.strftime('%Y-%m-%d %H:%M:%S') if job.last_run else 'Not Available',
        'next_run': job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else 'Not Scheduled',
        'setting_filefolder': bool(job.setting_filefolder)
    } for job in jobs]
    return jsonify(jobs_data)

@apis_other_bp.route('/api/unmatched_folders', methods=['GET'])
@login_required
@admin_required
def unmatched_folders():
    unmatched = UnmatchedFolder.query.join(Library).with_entities(
        UnmatchedFolder, Library.name.label('library_name'), Library.platform
    ).order_by(UnmatchedFolder.status.desc()).all()
    
    unmatched_data = [{
        'id': folder.id,
        'folder_path': folder.folder_path,
        'status': folder.status,
        'library_name': library_name,
        'platform_name': platform.name if platform else '',
        'platform_id': PLATFORM_IDS.get(platform.name) if platform else None
    } for folder, library_name, platform in unmatched]
    
    return jsonify(unmatched_data)



@apis_other_bp.route('/api/current_user_role', methods=['GET'])
@login_required
def get_current_user_role():
    return jsonify({'role': current_user.role}), 200

@apis_other_bp.route('/api/check_username', methods=['POST'])
@login_required
def check_username():
    print(F"Route: /api/check_username - {current_user.name} - {current_user.role}")    
    data = request.get_json()
    username = data.get('username')
    if not username:
        print(f"Check username: Missing username")
        return jsonify({"error": "Missing username parameter"}), 400
    print(f"Checking username: {username}")
    existing_user = User.query.filter(func.lower(User.name) == func.lower(username)).first()
    return jsonify({"exists": existing_user is not None})

@apis_other_bp.route('/api/search')
@login_required
def search():
    query = request.args.get('query', '')
    results = []
    if query:
        games = Game.query.filter(Game.name.ilike(f'%{query}%')).all()
        results = [{'id': game.id, 'uuid': game.uuid, 'name': game.name} for game in games]
    return jsonify(results)

@apis_other_bp.route('/api/get_libraries')
def get_libraries():
    # Direct query to the Library model
    libraries_query = Library.query.all()
    libraries = [
        {
            'uuid': lib.uuid,
            'name': lib.name,
            'image_url': lib.image_url if lib.image_url else url_for('static', filename='newstyle/default_library.jpg')
        } for lib in libraries_query
    ]
    print(f"Returning {len(libraries)} libraries.")
    return jsonify(libraries)
    
@apis_other_bp.route('/api/game_screenshots/<game_uuid>')
@login_required
def game_screenshots(game_uuid):
    screenshots = Image.query.filter_by(game_uuid=game_uuid, image_type='screenshot').all()
    screenshot_urls = [url_for('static', filename=f'library/images/{screenshot.url}') for screenshot in screenshots]
    return jsonify(screenshot_urls)

@apis_other_bp.route('/api/get_company_role', methods=['GET'])
@login_required
def get_company_role():
    game_igdb_id = request.args.get('game_igdb_id')
    company_id = request.args.get('company_id')
    # Validate input
    if not game_igdb_id or not company_id or not game_igdb_id.isdigit() or not company_id.isdigit():
        print("Invalid input: Both game_igdb_id and company_id must be provided and numeric.")
        return jsonify({'error': 'Invalid input. Both game_igdb_id and company_id must be provided and numeric.'}), 400
    try:
        print(f"Requested company role for Game IGDB ID: {game_igdb_id} and Company ID: {company_id}")
        
        response_json = make_igdb_api_request(
            "https://api.igdb.com/v4/involved_companies",
            f"""fields company.name, developer, publisher, game;
                where game={game_igdb_id} & id=({company_id});"""
        )
        
        if not response_json or 'error' in response_json:
            print(f"No data found or error in response: {response_json}")
            return jsonify({'error': 'No data found or error in response.'}), 404

        for company_data in response_json:
            company_info = company_data.get('company')
            if isinstance(company_info, dict):  # Ensure company_info is a dictionary
                company_name = company_info.get('name', 'Unknown Company')
            else:
                print(f"Unexpected data structure for company info: {company_info}")
                continue  # Skip this iteration
            role = 'Not Found'
            if company_data.get('developer', False):
                role = 'Developer'
            elif company_data.get('publisher', False):
                role = 'Publisher'

            print(f"Company {company_name} role: {role} (igdb_id={game_igdb_id}, company_id={company_id})")
            return jsonify({
                'game_igdb_id': game_igdb_id,
                'company_id': company_id,
                'company_name': company_name,
                'role': role
            }), 200
        return jsonify({'error': 'Company with given ID not found in the specified game.'}), 404

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({'error': 'An error occurred processing your request.'}), 500


@apis_other_bp.route('/api/get_cover_thumbnail', methods=['GET'])
@login_required
def get_cover_thumbnail():
    igdb_id = request.args.get('igdb_id', default=None, type=str)
    if igdb_id is None or not igdb_id.isdigit():
        return jsonify({'error': 'Invalid input. The ID must be numeric.'}), 400
    cover_url = get_cover_thumbnail_url(int(igdb_id))
    if cover_url:
        return jsonify({'cover_url': cover_url}), 200
    else:
        return jsonify({'error': 'Cover URL could not be retrieved.'}), 404


@apis_other_bp.route('/api/search_igdb_by_id')
@login_required
def search_igdb_by_id():
    igdb_id = request.args.get('igdb_id')
    if not igdb_id:
        return jsonify({"error": "IGDB ID is required"}), 400
    endpoint_url = "https://api.igdb.com/v4/games"
    query_params = f"""
        fields name, summary, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name, 
               screenshots.url, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
               aggregated_rating_count, rating, rating_count, status, category, total_rating,
               total_rating_count;
        where id = {igdb_id};
    """
    response = make_igdb_api_request(endpoint_url, query_params)
    if "error" in response:
        return jsonify({"error": response["error"]}), 500

    if response:
        game_data = response[0] if response else {}
        return jsonify(game_data)
    else:
        return jsonify({"error": "Game not found"}), 404


@apis_other_bp.route('/api/search_igdb_by_name')
@login_required
def search_igdb_by_name():
    game_name = request.args.get('name')
    platform_id = request.args.get('platform_id')

    if game_name:
        # Start with basic search and expand the query conditionally
        query = f"""
            fields id, name, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                   screenshots.url, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
                   aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                   total_rating_count;
            search "{game_name}";"""

        # Check if a platform_id was provided and is valid
        if platform_id and platform_id.isdigit():
            query += f" where platforms = ({platform_id});"
        else:
            query += ";"

        query += " limit 10;"  # limit results
        results = make_igdb_api_request('https://api.igdb.com/v4/games', query)

        if 'error' not in results:
            return jsonify({'results': results})
        else:
            return jsonify({'error': results['error']})
    return jsonify({'error': 'No game name provided'})


@apis_other_bp.route('/api/reorder_libraries', methods=['POST'])
@login_required
@admin_required
def reorder_libraries():
    try:
        new_order = request.json.get('order', [])
        for index, library_uuid in enumerate(new_order):
            library = Library.query.get(library_uuid)
            if library:
                library.display_order = index
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@apis_other_bp.route('/api/check_favorite/<game_uuid>')
@login_required
def check_favorite(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    is_favorite = game in current_user.favorites
    return jsonify({'is_favorite': is_favorite})

@apis_other_bp.route('/api/toggle_favorite/<game_uuid>', methods=['POST'])
@login_required
def toggle_favorite(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    
    if game in current_user.favorites:
        current_user.favorites.remove(game)
        is_favorite = False
    else:
        current_user.favorites.append(game)
        is_favorite = True
    
    db.session.commit()
    return jsonify({'success': True, 'is_favorite': is_favorite})


@apis_other_bp.route('/api/file_types/<string:type_category>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_file_types(type_category):
    if type_category not in ['allowed', 'ignored']:
        return jsonify({'error': 'Invalid type category'}), 400

    ModelClass = AllowedFileType if type_category == 'allowed' else IgnoredFileType

    if request.method == 'GET':
        types = ModelClass.query.order_by(ModelClass.value.asc()).all()
        return jsonify([{'id': t.id, 'value': t.value} for t in types])

    elif request.method == 'POST':
        data = request.get_json()
        new_type = ModelClass(value=data['value'].lower())
        try:
            db.session.add(new_type)
            db.session.commit()
            return jsonify({'id': new_type.id, 'value': new_type.value})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Type already exists'}), 400

    elif request.method == 'PUT':
        data = request.get_json()
        file_type = ModelClass.query.get_or_404(data['id'])
        file_type.value = data['value'].lower()
        try:
            db.session.commit()
            return jsonify({'id': file_type.id, 'value': file_type.value})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Type already exists'}), 400

    elif request.method == 'DELETE':
        file_type = ModelClass.query.get_or_404(request.get_json()['id'])
        db.session.delete(file_type)
        db.session.commit()
        return jsonify({'success': True})
    
@apis_other_bp.route('/check_path_availability', methods=['GET'])
@login_required
def check_path_availability():
    full_disk_path = request.args.get('full_disk_path', '')
    is_available = os.path.exists(full_disk_path)
    return jsonify({'available': is_available})


@apis_other_bp.route('/api/check_igdb_id')
@login_required
def check_igdb_id():
    igdb_id = request.args.get('igdb_id', type=int)
    if igdb_id is None:
        return jsonify({'message': 'Invalid request', 'available': False}), 400

    game_exists = check_existing_game_by_igdb_id(igdb_id) is not None
    return jsonify({'available': not game_exists})

@apis_other_bp.route('/api/delete_download/<int:request_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_download_request(request_id):
    try:
        download_request = DownloadRequest.query.get_or_404(request_id)
        
        # Check if zip file exists and is in the expected directory
        if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
            if download_request.zip_file_path.startswith(current_app.config['ZIP_SAVE_PATH']):
                try:
                    os.remove(download_request.zip_file_path)
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Error deleting ZIP file: {str(e)}'
                    }), 500
            else:
                print(f"Deleting download request: {download_request}")
                db.session.delete(download_request)
                db.session.commit()
                return jsonify({
                    'status': 'success',
                    'message': 'Download is not linked to a generated ZIP file. Only the download request has been removed.'
                }), 200
        print(f"Deleting download request: {download_request}")
        db.session.delete(download_request)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Download request deleted successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error deleting download request: {str(e)}'
        }), 500
