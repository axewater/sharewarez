# /modules/routes_apis/igdb.py
from flask import jsonify, request
from flask_login import login_required
from modules.utils_igdb_api import make_igdb_api_request, get_cover_thumbnail_url
from modules.utils_game_core import check_existing_game_by_igdb_id
from . import apis_bp

@apis_bp.route('/get_company_role', methods=['GET'])
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


@apis_bp.route('/get_cover_thumbnail', methods=['GET'])
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


@apis_bp.route('/search_igdb_by_id')
@login_required
def search_igdb_by_id():
    igdb_id = request.args.get('igdb_id')
    if not igdb_id:
        return jsonify({"error": "IGDB ID is required"}), 400
    endpoint_url = "https://api.igdb.com/v4/games"
    # Use the same field format as working scanning code
    query_params = f"""
        fields id, name, cover, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
               screenshots, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
               aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
               total_rating_count, storyline;
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


@apis_bp.route('/search_igdb_by_name')
@login_required
def search_igdb_by_name():
    game_name = request.args.get('name')
    platform_id = request.args.get('platform_id')

    if game_name:
        # Use the same field format as working scanning code  
        query_fields = """fields id, name, cover, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                          screenshots, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
                          aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                          total_rating_count, storyline;"""
        
        query_filter = f'search "{game_name}";'
        
        # Check if a platform_id was provided and is valid
        if platform_id and platform_id.isdigit():
            query_filter += f' where platforms = ({platform_id});'

        query_filter += " limit 10;"  # limit results
        query = query_fields + query_filter
        
        results = make_igdb_api_request('https://api.igdb.com/v4/games', query)

        if 'error' not in results:
            return jsonify({'results': results})
        else:
            return jsonify({'error': results['error']})
    return jsonify({'error': 'No game name provided'})

@apis_bp.route('/check_igdb_id')
@login_required
def check_igdb_id():
    igdb_id = request.args.get('igdb_id', type=int)
    if igdb_id is None:
        return jsonify({'message': 'Invalid request', 'available': False}), 400

    game_exists = check_existing_game_by_igdb_id(igdb_id) is not None
    return jsonify({'available': not game_exists})
