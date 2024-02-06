# jellyfin-favorites-dump

Easily dump all of your favorite music to a mp3 player of your choice.

This is a simple script to gather and dump all of your favorited music to a directory, intended for use with [syncthing](https://github.com/syncthing/syncthing). Audio files are transcoded to V2 MP3s, preserving metadata.

## Usage

The only non-standard library required is `requests`, which can be installed using `apt install python3-requests` if it hasn't been already. The transcoding relies on `ffmpeg`, which should already be installed if you're using Jellyfin.

Some configuration is required in `config.json`:
- `SERVER_URL`: The URL of your Jellyfin server, defaults to localhost.
- `API_KEY`: Your Jellyfin API key, which can be found in the dashboard under "Advanced".
- `USER_ID`: Your Jellyfin user ID. When on your user page, this is located in the url.
- `SYNC_FOLDER`: The directory to sync to. This is the directory that will be filled with your favorited music. Defaults to something in `/tmp`, change to your desired file system location.

Once these dependencies are met and the config is set, I recommend simply setting up a cron task to run the script at a regular interval.