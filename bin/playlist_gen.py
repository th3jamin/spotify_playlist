#!/usr/bin/env python
import requests, sys, getopt, json, math, subprocess, string, signal, time, threading
from pprint import pprint
from Naked.toolshed.shell import execute_js, muterun_js, muterun, execute

def signal_handler(signal, frame):
    sys.exit(0)

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
    p = muterun(command)

def startNodeServer():
    success = muterun_js('../app.js')

def playlistThread(playlist, user):
    print "Please visit the following to login to spotify: http://localhost:8888, once complete and you see the token page, come back and hit enter"
    input("Press Enter to continue...")

    #r = requests.get("http://localhost:8888/token")
    json = json.loads(execute("curl -X GET http://localhost:8888/token"))
    if json["access_token"]:
        print "Received valid access token: %s" % (json['access_token'])
    else:
        print "You must not have logged into Spotify at http://localhost:8888, cannot get access_token"
        return

    token = json['access_token']
    playlistJson = findPlaylist(token, user, playlist)
    if playlistJson == None:
        print "Could not find playlist"
    else:
        for track in extractTracksFromPlaylist(playlistJson['tracks']['href'], token):
            doRecordTrack(track)
    return

def wait(t):
    main_thread = threading.currentThread()
    if t is not main_thread:
        t.join()

def main(argv):
    # handle ctrl+c
    signal.signal(signal.SIGINT, signal_handler)

    playlist = ''
    user = ''

    # exactly 3 args!
    if len(argv) != 4:
        usage()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv,"p:u:h",["playlist=", "user="])
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
    print 'Playlist is "', playlist
    print 'User is "', user

    nodeThread = threading.Thread(target=startNodeServer)
    nodeThread.setDaemon(True)
    mainThread = threading.Thread(target=playlistThread, args=(playlist, user))
    nodeThread.start()
    #mainThread.start()
    print "Please visit the following to login to spotify: http://localhost:8888, once complete and you see the token page, come back and hit enter"
    raw_input("Press Enter to continue...")

    r = requests.get("http://localhost:8888/token")
    json = r.json()
    if json.get('access_token'):
        print "Received valid access token: %s" % (json['access_token'])
    else:
        print "You must not have logged into Spotify at http://localhost:8888, cannot get access_token"
        return

    token = json['access_token']
    playlistJson = findPlaylist(token, user, playlist)
    if playlistJson == None:
        print "Could not find playlist"
    else:
        for track in extractTracksFromPlaylist(playlistJson['tracks']['href'], token):
            wait(threading.Thread(target=doRecordTrack(track), args=(track)).setDaemon(True).start())

    sys.exit(2)

if __name__ == '__main__':
    main(sys.argv[1:])

