# spotify_playlist
* Mac OSX Only Application

## Dependencies
* node, npm, python, homebrew 
* [soundflower](soundflower/) (included)
* quicktime player
* spotify player

## Setup
* Use the included initialize.sh script to auto setup your node and python dependencies
* You will need a Spotify App Client ID and Client Secret: [Spotify Applications Manager](https://developer.spotify.com/my-applications) 

## Execution
* ./bin/playlist_gen.py -p '\{Spotify playlist name\}'
* You then need to visit [http://localhost:8888](http://localhost:8888) and login to the spotify API
* After you are presented with a token you can go back to your console and continue

## WIPs
* Automatic ad-detection and removal

## ToDos
* Add a command line tagging library to make the output files more easily integrated into music players
