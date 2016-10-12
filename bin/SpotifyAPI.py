import requests, sys, getopt, json, math, os
from Naked.toolshed.shell import muterun
from mutagen.mp4 import MP4, MP4Cover, MP4StreamInfoError
from time import sleep

class SpotifyTrack:
    name = ""
    duration = 0
    album = ""
    artist = ""
    track_num = 0
    disc_num = 0
    artwork_url = ""
    uri = ""

    def getDurationSeconds(self, n=0):
    	return int(math.ceil(self.duration / 1000.0)) + n

    # process the JSON for this Spotify Track
    def processJson(self, j):
        self.uri = j["track"]["uri"]
    	self.name = j["track"]["name"].replace('/', ':')
    	self.duration = j["track"]["duration_ms"]
    	self.track_num = j["track"]["track_number"]
    	self.artwork_url = j["track"]["album"]["images"][0]["url"]
    	self.album = j["track"]["album"]["name"]
    	self.artist = j["track"]["artists"][0]["name"]
    	self.disc_num = j["track"]["disc_number"]

    def loadArtwork(self, url):
    	r = muterun('curl -X GET "%s" -o /tmp/cover.jpeg' % (url))
    	if r.exitcode != 0:
    		print "Failed to retrieve artwork from url=%s" % (url)
    		return False
    	return True

    def sanitize(self, filename):
        return filename.replace('/', ':')

    def tag(self, filename, withRetry=True):
        if os.path.isfile(filename):
            # tag the track, need to loop because the export process in non-deterministic
            while withRetry:
                try:
                    f = MP4(filename)
                    f.tags['\xa9nam'] = self.name
                    f.tags['\xa9alb'] = self.album
                    f.tags['\xa9ART'] = self.artist
                    f.tags['trkn'] = [(self.track_num,self.track_num)]
                    f.tags['disk'] = [(self.disc_num,self.disc_num)]
                    if self.loadArtwork(self.artwork_url):
                        with open("/tmp/cover.jpeg", "rb") as art:
                            f.tags["covr"] = [
                                MP4Cover(art.read(), imageformat=MP4Cover.FORMAT_JPEG)
                            ]
                        os.remove('/tmp/cover.jpeg')
                    f.save()
                    break
                except MP4StreamInfoError:
                    sleep(1)

    def __init__(self, j):
    	self.processJson(j)
