import json, os, math
from Naked.toolshed.shell import muterun 
from mutagen.mp4 import MP4, MP4Cover

class SpotifyTrack:
    name = ""
    duration = 0
    album = ""
    artist = ""
    track_num = 0
    disc_num = 0
    artwork_url = ""
    uri = ""

    def getDurationSeconds(self):
    	return int(math.ceil(self.duration / 1000.0))

    # process the JSON for this Spotify Track
    def processJson(self, j):
        self.uri = j["track"]["uri"]
    	self.name = j["track"]["name"]
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

    def tag(self, filename):
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

    def __init__(self, j):
    	self.processJson(j)
