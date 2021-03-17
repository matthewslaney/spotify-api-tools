"""
Prerequisites

    pip3 install spotipy Flask Flask-Session

    // from your [app settings](https://developer.spotify.com/dashboard/applications)
    export SPOTIPY_CLIENT_ID=client_id_here
    export SPOTIPY_CLIENT_SECRET=client_secret_here
    export SPOTIPY_REDIRECT_URI='http://127.0.0.1:7777' // must contain a port

    // on Windows, use `SET` instead of `export`

Run app.py

    python3 -m flask run --port=7777
"""

import os
from flask import Flask, session, request, redirect
from flask_session import Session
import flask_excel as excel
import spotipy
import uuid
import pprint
import pandas as pd
from collections import defaultdict

DEBUG = True
app = Flask(__name__)
excel.init_excel(app)
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)



caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)


@app.route('/')
def index():
    if not session.get('uuid'):
        # Step 1. Visitor is unknown, give random ID
        session['uuid'] = str(uuid.uuid4())
    all_spotify_scope = '''
        user-library-read
        playlist-modify-private
        ugc-image-upload
        user-read-recently-played
        user-top-read
        user-read-playback-position
        user-read-playback-state
        user-modify-playback-state
        user-read-currently-playing
        app-remote-control
        streaming
        playlist-modify-public
        playlist-modify-private
        playlist-read-private
        playlist-read-collaborative
        user-follow-modify
        user-follow-read
        user-library-modify
        user-library-read
        user-read-email
        user-read-private
    '''
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path(), show_dialog=True, scope=all_spotify_scope)
    if request.args.get("code"):
        # Step 3. Being redirected from Spotify auth page
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')

    if not auth_manager.get_cached_token():
        # Step 2. Display sign in link when no token
        auth_url = auth_manager.get_authorize_url()
        return f'<h2><a href="{auth_url}">Sign in</a></h2>'

    # Step 4. Signed in, display data
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    return f'<h2>Hi {spotify.me()["display_name"]}, ' \
           f'<small><a href="/sign_out">[sign out]<a/></small></h2>' \
           f'<a href="/playlists">my playlists</a>' \
           f'<form method="POST" action="/getplaylistbyid"><input type="text" name="playlistid"><input type="submit" value="CSV of Playlist by ID"></form>' \
           f'<form method="GET" action="/getallplaylists"><input type="submit" value="CSV of All Playlists"></form>'


@app.route('/sign_out')
def sign_out():
    os.remove(session_cache_path())
    session.clear()
    return redirect('/')


@app.route('/playlists')
def playlists():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())

    if not auth_manager.get_cached_token():
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    return spotify.current_user_playlists()

@app.route('/getallplaylists')
def getallplaylists():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())

    if not auth_manager.get_cached_token():
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    allplaylists = spotify.current_user_playlists(offset=50)['items']
    full_tracklist = []
    for playlist in allplaylists:
        current_tracklist, current_playlist_name = playlist_to_tracklist(playlist['id'])
        for track in current_tracklist:
            track['playlist_id'] = playlist['id']
            track['Playlist Name'] = current_playlist_name
        full_tracklist = full_tracklist + current_tracklist
    output = excel.make_response_from_records(full_tracklist, 'csv')
    output_filename = "All Playlists.csv"
    output.headers["Content-Disposition"] = "attachment; filename=" + output_filename
    output.headers["Content-type"] = "text/csv"
    return output


@app.route('/getplaylistbyid', methods=['GET', 'POST'])
def getplaylistbyid():
    playlistid = request.form['playlistid']
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    tracklist, playlist_name = playlist_to_tracklist(playlistid)
    output = excel.make_response_from_records(tracklist, 'csv')
    output_filename = playlist_name + " - " + playlistid + ".csv"
    output.headers["Content-Disposition"] = "attachment; filename=" + output_filename
    output.headers["Content-type"] = "text/csv"
    return output


def session_cache_path():
    return caches_folder + session.get('uuid')

def playlist_to_tracklist(playlistid):
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    playlist_main = spotify.playlist(playlistid)
    tracks =[]
    for track in playlist_main['tracks']['items']:
        if track['track'] and track['track']['id']:
            tracks.append(track)
    # tracks = playlist_main['tracks']['items']
    tidlist = [ track['track']['id'] for track in tracks ]
    audio_features = spotify.audio_features(tidlist)
    has_next = playlist_main['tracks']['next']
    offset = playlist_main['tracks']['limit']
    while has_next:
        additional_playlist_tracks = spotify.playlist_tracks(playlistid, offset=offset)
        additional_tracks = []
        for track in additional_playlist_tracks['items']:
            if track['track'] and track['track']['id']:
                additional_tracks.append(track)
        tracks = tracks + additional_tracks
        tidlist = [ track['track']['id'] for track in additional_tracks ]
        audio_features = audio_features + spotify.audio_features(tidlist)
        has_next = additional_playlist_tracks['next']
        offset += additional_playlist_tracks['limit']
    tracklist = []
    for track_item in tracks:
        track = track_item['track']
        track_id = track['id']
        try:
            track_audio_features = [af for af in audio_features if af['id'] == track_id][0]
        except:
            print(track_id)
            track_audio_features = defaultdict(dict)
        other_artists = []
        if len(track['artists']) > 1:
            for artist in track['artists'][1:]:
                other_artists.append(artist['name'])
        new_track = {
            'artist': track['artists'][0]['name'],
            'other_artists': other_artists,
            'name': track['name'],
            'id': track['id'],
            'duration': track['duration_ms'],
            'url': track['external_urls']['spotify'],
            'popularity': track['popularity'],
            'album': track['album']['id'],
            'release_date': track['album']['release_date'],
            'acousticness': track_audio_features['acousticness'],
            'danceability': track_audio_features['danceability'],
            'energy': track_audio_features['energy'],
            'instrumentalness': track_audio_features['instrumentalness'],
            'key': track_audio_features['key'],
            'liveness': track_audio_features['liveness'],
            'loudness': track_audio_features['loudness'],
            'mode': track_audio_features['mode'],
            'speechiness': track_audio_features['speechiness'],
            'tempo': track_audio_features['tempo'],
            'time_signature': track_audio_features['time_signature'],
            'valence': track_audio_features['valence'],
        }
        tracklist.append(new_track)
    playlist_name = playlist_main['name']
    return tracklist, playlist_name