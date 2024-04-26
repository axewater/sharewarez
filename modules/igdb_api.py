# File: /modules/igdb_api.py
# This file contains functions for interacting with the IGDB API extracted from routes.py

import requests
from config import Config

def make_igdb_api_request(endpoint, query):
    headers = {
        'Client-ID': Config.IGDB_CLIENT_ID,
        'Authorization': f'Bearer {Config.IGDB_ACCESS_TOKEN}',
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