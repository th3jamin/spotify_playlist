#!/usr/bin/env python
import requests, sys, getopt, json, math, subprocess, string
from pprint import pprint

def makeAppleScriptCommand(name, duration, track):
    return """set filePath to (path to home folder as text) & "%s.m4a"
tell application "QuickTime Player"
    activate
    set new_recording to (new audio recording)
    tell new_recording
        start
        tell application "Spotify"
            play track "%s"
        end tell
        delay %s
        stop
        tell application "Spotify"
            stop
        end tell
    end tell
    
    open for access file filePath
    close access file filePath
    export (first document) in filePath using settings preset "Audio Only"
    close (first document) without saving
end tell""" % (sanitizeName(name), track, duration)

def sanitizeName(name):
    exclude = set(string.punctuation)
    return ''.join(ch for ch in name if ch not in exclude)

def convertToSeconds(millis):
    return int(math.ceil(millis/1000))

def usage():
    print 'playlist_gen.py -t <oauth-token> -p <playlist-name> -u <spotify-user>'

def findPlaylist(token, user, name):
    # loop trough all playlists until we find or exhaust, 
    # then call ourselves if we have another playlist
    limit = 50
    url = "https://api.spotify.com/v1/users/%s/playlists?offset=0&limit=%s" % (user, limit)
    return findPlaylist_internal(url, token, user, name)

def findPlaylist_internal(url, token, user, name):
    # loop trough all playlists until we find or exhaust, 
    # then call ourselves if we have another playlist
    auth = "Bearer %s" % (token)
    response = requests.get(url, headers={"Authorization" : auth})

    if response.status_code != 200:
        print "Could not retrieve from Spotify API: " + response.text
        return None

    json = response.json()

    for list in json["items"]:
        if list["name"].lower() == name.lower():
            return list
    
    if json.get('next'):
        return findPlaylist_internal(json["next"], token, user, name)

def extractTracksFromPlaylist(url, token):
    # need to extract a list of tuples
    auth = "Bearer %s" % (token)
    response = requests.get(url, headers={"Authorization" : auth})

    if response.status_code != 200:
        print "Could not retrieve from Spotify API: " + response.text
        return None

    json = response.json()
    tracks = []

    for item in json["items"]:
        name = item['track']['name']
        duration = convertToSeconds(item['track']['duration_ms']) + 1 # add buffer
        uri = item['track']['uri']
        tracks.append((name,duration,uri))        
    
    if json.get('next'):
        tracks = tracks + extractTracksFromPlaylist(json["next"], token)

    return tracks

def doRecordTrack(track):
    script = makeAppleScriptCommand(track[0],track[1],track[2])
    command = "osascript -e '%s'" % (script)
    print "Processing track: %s, %s, %s" % (track[0],track[1],track[2])
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    print process.returncode

def main(argv):
    token = ''
    playlist = ''
    user = ''

    # exactly 3 args!
    if len(argv) != 6:
        usage()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv,"t:p:u:h",["token=","playlist=", "user="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt in ("-t", "--token"):
            token = arg
        elif opt in ("-p", "--playlist"):
            playlist = arg
        elif opt in ("-u", "--user"):
            user = arg
    print 'Token is "', token
    print 'Playlist is "', playlist
    print 'User is "', user

    playlistJson = findPlaylist(token, user, playlist)
    if playlistJson == None:
        print "Could not find playlist"
    else:
        for track in extractTracksFromPlaylist(playlistJson['tracks']['href'], token):
            doRecordTrack(track)

if __name__ == '__main__':
    main(sys.argv[1:])

