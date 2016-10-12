#!/usr/bin/env python
import requests, sys, getopt, json, math, subprocess, string, signal, time, threading, os, errno, getpass
from pprint import pprint
from Naked.toolshed.shell import execute_js, muterun_js, muterun, execute
from SpotifyAPI import SpotifyTrack

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def trackExists(path, name):
    return os.path.isfile("%s/%s.m4a" % (path, name))

def signal_handler(signal, frame):
    script = """
    tell application "Spotify"
        pause
    end tell
    tell application "QuickTime Player"
        tell (first document)
            stop
        end tell
    end tell
    """
    command = "osascript -e '%s'" % (script)
    muterun(command)
    script = """
    tell application "QuickTime Player"
        ignoring application responses
            close (first document) without saving
            quit
        end ignoring
    end tell
    """
    command = "osascript -e '%s'" % (script)
    muterun(command)
    sys.exit(0)

def makeAppleScriptCommand(track, playlist):
    return """set filePath to (path to music folder as text) & \\"%s:%s.m4a\\"
tell application \\"QuickTime Player\\"
    set track_dur to %s
    set ad_delay to 3
    set new_recording to (new audio recording)
    tell new_recording
        start
        tell application \\"Spotify\\"
            play track \\"%s\\"
        end tell
        display notification (\\"Recording track: %s - %s\\") with title(\\"Spotify Playlist Recorder\\")
        delay ad_delay
        tell application \\"Spotify\\"
            tell current track
                set u to spotify url
                set playedAd to u contains \\"spotify:ad\\"
                set d to duration
            end tell
        end tell
        if playedAd then
            delay (track_dur + d - ad_delay)
        else
            delay (track_dur - ad_delay)
        end if
        stop
        tell application \\"Spotify\\"
            pause
        end tell
    end tell
    -- trim the ad
    if playedAd then
        tell (first document)
            set dd to duration
            trim from d to dd
        end tell
    end if
    open for access file filePath
    close access file filePath
    export (first document) in filePath using settings preset \\"Audio Only\\"
    close (first document) without saving
end tell""" % (playlist, track.name, track.getDurationSeconds(), track.uri, track.name, track.artist)

def sanitizeName(name):
    exclude = set(string.punctuation)
    return ''.join(ch for ch in name if ch not in exclude)

def usage():
    print 'PlaylistGen.py -t -p <playlist-name>'

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
        s =  SpotifyTrack(item)
        tracks.append(s)

    if json.get('next'):
        tracks = tracks + extractTracksFromPlaylist(json["next"], token)

    return tracks

def doRecordTrack(track, playlist, filename):
    script = makeAppleScriptCommand(track, playlist)
    command = "osascript -e \"%s\"" % (script)
    print "Processing track: %s, %s, %s" % (track.name, track.getDurationSeconds(), track.uri)
    p = muterun(command)
    if p.exitcode != 0:
        print p.stderr
    # delay to let quicktime finish export
    print "Waiting for QuickTime export to finish..."
    time.sleep(1)
    print "Tagging track %s" % (track.name)
    track.tag(filename, True)

def startNodeServer():
    dir_path = os.path.dirname(os.path.realpath(__file__)) + "/../app.js"
    success = muterun_js(dir_path)

def wait(t):
    main_thread = threading.currentThread()
    if t is not main_thread:
        t.join()

def stopNodeServer():
    # force kill the node server and its thread
    cmd = """ps -ef | grep -e "[s]potify_playlist/.*/app.js" | awk '{print $2}'"""
    r = muterun(cmd)
    if r.exitcode == 0:
        for p in r.stdout.splitlines():
            if execute("kill -2 %s" % (p)):
                print "stopped local server successfully"
            else:
                print "couldn't stop local server :("
    else:
        print "no local server found, doing nothing"

def main(argv):
    # handle ctrl+c
    signal.signal(signal.SIGINT, signal_handler)

    playlist = ''
    tag_only = False

    # exactly 3 args!
    if len(argv) != 2 and len(argv) != 3:
        usage()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv,"p:ht",["playlist="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt == '-t':
            tag_only = True
        elif opt in ("-p", "--playlist"):
            playlist = unicode(arg, 'utf_8')
    print 'Playlist is "', playlist

    # start the node server in its own thread
    nodeThread = threading.Thread(target=startNodeServer)
    nodeThread.setDaemon(True)
    nodeThread.start()

    print "Please visit the following to login to spotify: http://localhost:8888, come back and hit enter when logged in"
    print ""

    # open the page for them!!!
    execute('open "http://localhost:8888"')

    # wait for user to login
    raw_input("Press Enter to continue...")

    # get a token from our local /tmp cache
    token_file = '/tmp/spotify_tokens.json'
    if os.path.isfile(token_file):
        with open(token_file) as data_file:
            j = json.load(data_file)
    else:
        print "You must not have logged into Spotify at http://localhost:8888, cannot get access_token"
        stopNodeServer()
        sys.exit(2)

    # load the json token
    if j.get('access_token'):
        print "Received valid access token: %s" % (j['access_token'])
    else:
        print "You must not have logged into Spotify at http://localhost:8888, cannot get access_token"
        stopNodeServer()
        sys.exit(2)

    # delete the token file
    os.remove(token_file)

    # we don't need the local http anymore
    stopNodeServer()
    token = j['access_token']

    # start processing at the default playlist for this user
    playlistJson = findPlaylist('https://api.spotify.com/v1/me/playlists', token, playlist)

    # if we found it get all the tracks as a tuple3 and spin off a thread to record
    if playlistJson == None:
        print "Could not find playlist"
    else:
        # make the output dir beforehand
        output_dir = "/Users/%s/Music/%s" % (getpass.getuser(), playlist)
        print "Making output directory: " + output_dir
        mkdir_p(output_dir)
        for track in extractTracksFromPlaylist(playlistJson['tracks']['href'], token):
            filename = '%s/%s.m4a' % (output_dir, track.name)
            if os.path.isfile(filename):
                if tag_only:
                    print "Tagging track %s" % (track.name)
                    track.tag(filename, True)
                else:
                    print "Track: '%s' already exists in output directory skipping..." % (track.name)
            else:
                wt = threading.Thread(target=doRecordTrack, args=[track, playlist, filename])
                wt.setDaemon(True)
                wt.start()
                wait(wt)

    signal_handler(None, None)

if __name__ == '__main__':
    main(sys.argv[1:])

