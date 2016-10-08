#!/usr/bin/env python
import requests, sys, getopt, json, math, subprocess, string, signal, time, threading, os, errno, getpass
from pprint import pprint
from Naked.toolshed.shell import execute_js, muterun_js, muterun, execute

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def signal_handler(signal, frame):
    sys.exit(0)

def makeAppleScriptCommand(name, duration, track, playlist):
    return """set filePath to (path to music folder as text) & "%s:%s.m4a"
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
end tell""" % (sanitizeName(playlist), sanitizeName(name), track, duration)

def sanitizeName(name):
    exclude = set(string.punctuation)
    return ''.join(ch for ch in name if ch not in exclude)

def convertToSeconds(millis):
    return int(math.ceil(millis/1000))

def usage():
    print 'playlist_gen.py -p <playlist-name>'

def findPlaylist(url, token, name):
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
        return findPlaylist(json["next"], token, name)
    else:
        return None

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

def doRecordTrack(track, playlist):
    script = makeAppleScriptCommand(track[0],track[1],track[2], playlist)
    command = "osascript -e '%s'" % (script)
    print "Processing track: %s, %s, %s" % (track[0],track[1],track[2])
    p = muterun(command)
    time.sleep(3) # deply to let quicktime do its thing

def startNodeServer():
    dir_path = os.path.dirname(os.path.realpath(__file__)) + "/../app.js"
    success = muterun_js(dir_path)

def wait(t):
    main_thread = threading.currentThread()
    if t is not main_thread:
        t.join()

def main(argv):
    # handle ctrl+c
    signal.signal(signal.SIGINT, signal_handler)

    playlist = ''

    # exactly 3 args!
    if len(argv) != 2:
        usage()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv,"p:h",["playlist="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt in ("-p", "--playlist"):
            playlist = unicode(arg, 'utf_8')
    print 'Playlist is "', playlist

    # start the node server in its own thread
    nodeThread = threading.Thread(target=startNodeServer)
    nodeThread.setDaemon(True)
    nodeThread.start()

    print "Please visit the following to login to spotify: http://localhost:8888, come back and hit enter when logged in"
    print ""

    # wait for user to login
    raw_input("Press Enter to continue...")

    # get a token from our local /tmp cache
    token_file = '/tmp/spotify_tokens.json'
    if os.path.isfile(token_file):
        with open(token_file) as data_file:
            j = json.load(data_file)
    else:
        print "You must not have logged into Spotify at http://localhost:8888, cannot get access_token"
        sys.exit(2)

    # load the json token
    if j.get('access_token'):
        print "Received valid access token: %s" % (j['access_token'])
    else:
        print "You must not have logged into Spotify at http://localhost:8888, cannot get access_token"
        return

    token = j['access_token']

    # start processing at the default playlist for this user
    playlistJson = findPlaylist('https://api.spotify.com/v1/me/playlists', token, playlist)

    # if we found it get all the tracks as a tuple3 and spin off a thread to record
    if playlistJson == None:
        print "Could not find playlist"
    else:
        # make the output dir beforehand
        output_dir = "/Users/%s/Music/%s" % (getpass.getuser(), sanitizeName(playlist))
        print "Making output directory: " + output_dir
        mkdir_p(output_dir)
        for track in extractTracksFromPlaylist(playlistJson['tracks']['href'], token):
            wt = threading.Thread(target=doRecordTrack, args=[track, playlist])
            wt.setDaemon(True)
            wt.start()
            wait(wt)

if __name__ == '__main__':
    main(sys.argv[1:])

