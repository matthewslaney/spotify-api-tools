# This script downloads a Spotify playlist and outputs a CSV file with the list of tracks.

import json
import csv
import urllib.request
import urllib.parse


def playlist_to_csv(playlist_id, spotify_token, output_filename):
    request_headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + spotify_token,
    }

    api_url = (
        'https://api.spotify.com/v1/playlists/' + playlist_id +
        '/tracks?fields=items(track(name%2Chref%2Cartists))&limit=100&offset=0'
    )

    request_object = urllib.request.Request(api_url, headers=request_headers)
    json_data = urllib.request.urlopen(request_object).read()

    playlistdict = json.loads(json_data)

    # This will be a list of dictionaries
    playlist = []

    for trackjs in playlistdict['items']:
        track = trackjs['track']
        trackdict = {}
        trackdict['Title'] = track['name']
        # For simplicity, we take only the first listed artist
        trackdict['Artist'] = track['artists'][0]['name']
        try:
            # Modify the link so that it can be used in browser rather than only via API
            trackdict['Link'] = track['href'].replace('https://api.spotify.com/v1/tracks/','https://open.spotify.com/track/')
        except:
            # If uploaded items are in playlist, there will be no Spotify URL
            trackdict['Link'] = 'No URL'
        playlist.append(trackdict)

    with open(output_filename, 'w') as outputfile:
        fieldnames = ['Title', 'Artist', 'Link']
        writer = csv.DictWriter(outputfile, fieldnames=fieldnames)
        writer.writeheader()
        for track in playlist:
            writer.writerow(track)

if __name__ == '__main__':
    print('This script downloads a playlist and outputs a CSV file with the list of tracks.')
    playlist_id = input('Please input playlist id: ')
    spotify_token = input('Please input Spotify token: ')
    output_filename = input('Please choose a filename for the CSV output: ')
    playlist_to_csv(playlist_id, spotify_token, output_filename)