@bp.route('/api/search')
@login_required
def search():
    query = request.args.get('query', '')
    results = []

@bp.route('/toggle_favorite/<game_uuid>', methods=['POST'])
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

@bp.route('/favorites')
@login_required
def favorites():
    page = request.args.get('page', 1, type=int)
    per_page = current_user.preferences.items_per_page if current_user.preferences else 20
    
    # Create a proper query for pagination
    favorites_query = Game.query.join(user_favorites).filter(
        user_favorites.c.user_id == current_user.id
    )
    pagination = favorites_query.paginate(page=page, per_page=per_page, error_out=False)
    games = pagination.items
    
    # Process game data for display
    game_data = []
    for game in games:
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else 'newstyle/default_cover.jpg'
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        
        game_data.append({
            'id': game.id,
            'uuid': game.uuid,
            'name': game.name,
            'cover_url': cover_url,
            'summary': game.summary,
            'url': game.url,
            'size': game_size_formatted,
            'genres': genres
        })
    
    return render_template('games/favorites.html', 
                         games=game_data,
                         pagination=pagination)

@bp.route('/check_favorite/<game_uuid>')
@login_required
def check_favorite(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    is_favorite = game in current_user.favorites
    return jsonify({'is_favorite': is_favorite})

    if query:
        games = Game.query.filter(Game.name.ilike(f'%{query}%')).all()
        results = [{'id': game.id, 'uuid': game.uuid, 'name': game.name} for game in games]

        # print(f'Search results for "{query}": {results}')
    return jsonify(results)
