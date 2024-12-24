# File: /modules/igdb_api.py
# This file contains functions for interacting with the IGDB API extracted from routes.py

import requests
from flask import current_app
from modules.models import GlobalSettings

def make_igdb_api_request(endpoint, query):
    settings = GlobalSettings.query.first()
    if not settings or not settings.igdb_access_token:
        raise ValueError("IGDB API settings not configured or access token missing")
        
    headers = {
        'Client-ID': settings.igdb_client_id,
        'Authorization': f'Bearer {settings.igdb_access_token}',
        'Accept': 'application/json'
    }
    response = requests.post(endpoint, headers=headers, data=query)
    return response.json()

def get_cover_thumbnail_url(igdb_id):
    endpoint = "https://api.igdb.com/v4/covers"
    query = f"fields url; where game={igdb_id};"
    response = make_igdb_api_request(endpoint, query)
    if response:
        return response[0]['url']
    return None