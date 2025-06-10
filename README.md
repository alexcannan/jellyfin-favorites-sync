# jellyfin-favorites-sync

Easily sync all of your favorite music from Jellyfin to an mp3 player of your choice.

This is a simple script to gather and dump all of your favorited music to a directory, perhaps for use with [syncthing](https://github.com/syncthing/syncthing) or `rsync`. Audio files are transcoded to V0 MP3s, preserving metadata. Album covers are also downloaded and saved as `cover.$ext` in the album directory.

## Usage

### Dependencies

The only non-standard library required is `requests`, which can be installed using `apt install python3-requests` if it hasn't been already. The transcoding relies on `ffmpeg`, which should already be installed if you're using Jellyfin, though you may have to add it to your PATH.

### Environment Variables

- `JFS_SERVER_URL`: The URL of your Jellyfin server, defaults to localhost.
- `JFS_API_KEY`: Your Jellyfin API key, which can be found in the dashboard under "Advanced".
- `JFS_USER_ID`: Your Jellyfin user ID. When on your user page, this is located in the url.
- `JFS_SYNC_FOLDER`: The directory to sync to. This is the directory that will be filled with your favorited music. Defaults to something in `/tmp` (which will be emptied on shutdown), change to your desired file system location for persistence.

### Scheduling

Once these dependencies are met and the config is set, I recommend simply setting up a cron task to run the script at a regular interval. For example, to run it every night at 3:00 AM, open your crontab with `crontab -e` and add the line `0 3 * * * python3 /path/to/jellyfin-favorites-dump/pull.py`.

### Platform Support

This script has only been tested on Linux, but I expect it to work on any platform that supports Python and ffmpeg. If you have any issues, please open an issue and I will do my best to help.

## Alternative Formats

The script is hardcoded to transcode to V0 MP3s, but this can be easily changed inside the `sync_audio` function if you have different ffmpeg arguments in mind. If you want to use a different codec altogether, remember to change the extension hardcoded in the `sync_filepath` property of the `Audio` class.

## Future Work

I encourage anyone to open an issue if they have any feature requests or bug reports. In the meantime, I will continue to develop this for my personal use.
