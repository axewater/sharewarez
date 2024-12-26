# File: /modules/igdb_api.py
# This file contains functions for interacting with the IGDB API extracted from routes.py

import requests
from flask import current_app
from modules.models import GlobalSettings



def make_igdb_api_request(endpoint_url, query_params):
    # Get IGDB settings from database
    settings = GlobalSettings.query.first()
    if not settings or not settings.igdb_client_id or not settings.igdb_client_secret:
        return {"error": "IGDB settings not configured in database"}

    access_token = get_access_token(settings.igdb_client_id, settings.igdb_client_secret) 

    if not access_token:
        return {"error": "Failed to retrieve access token"}

    headers = {
        'Client-ID': settings.igdb_client_id,
        'Authorization': f"Bearer {access_token}"
    }

    try:
        # print(f"make_igdb_api_request Attempting to make a request to {endpoint_url} with headers: {headers} and query: {query_params}")
        response = requests.post(endpoint_url, headers=headers, data=query_params)
        response.raise_for_status()
        data = response.json()
        # print(f"make_igdb_api_request Response from IGDB API: {data}")
        return response.json()

    except requests.RequestException as e:
        return {"error": f"make_igdb_api_request API Request failed: {e}"}

    except ValueError:
        return {"error": "make_igdb_api_request Invalid JSON in response"}

    except Exception as e:
        return {"error": f"make_igdb_api_request An unexpected error occurred: {e}"}
    
def get_access_token(client_id, client_secret):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        print("Failed to obtain access token")
        return None
