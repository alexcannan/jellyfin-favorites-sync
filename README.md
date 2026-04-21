# jellyfin-favorites-sync

Gather and dump all of your favorited music from Jellyfin to a directory, perhaps for use with [rsync](https://linux.die.net/man/1/rsync) or [syncthing](https://github.com/syncthing/syncthing) onto an mp3 player of your choice. Audio files are transcoded to V0 MP3s by default, preserving metadata. Album covers are also downloaded and saved as `cover.$ext` in the album directory.

## Usage

### Dependencies

No non-standard Python libraries are required. The transcoding relies on `ffmpeg`, which should already be installed if you're using Jellyfin, though you may have to add it to your PATH.

### Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `JFS_API_KEY` | yes | - | Your Jellyfin API key, which can be found in the dashboard under "Advanced". |
| `JFS_USER_ID` | yes | - | Your Jellyfin user ID. When on your user page, this is located in the url. |
| `JFS_SERVER_URL` | no | `http://localhost:8096` | The URL of your Jellyfin server. |
| `JFS_SYNC_FOLDER` | no | `/tmp/jellyfin-favorites-sync` | The directory to sync to. The default is in `/tmp` (which will be emptied on shutdown), change to your desired file system location for persistence. |
| `JFS_TARGET` | no | `mp3-v0` | Transcode target. `mp3-v0` (V0 MP3), `ogg-q6` (Vorbis q6), `opus-128` (Opus 128kbps) are available out of the box. Files already in the target format are copied verbatim instead of re-encoded. Other target configurations can be added under `TARGETS` in `pull.py`. |

### Dry Run

Pass `--dry-run` to print the output filepaths without transcoding, copying, or deleting anything. Useful for previewing what a sync will produce. Example output:

```
> python3 pull.py --dry-run | grep jadeworm
2026-04-20 21:20:53,121 - INFO - fetching favorited music from jellyfin
2026-04-20 21:21:09,073 - INFO - 32 song(s) favorited, now gathering songs from 1056 favorited Artists/Albums
fetching: 1056/1056 [100%] 80s<0s
/tmp/jellyfin-favorites-sync/jadeworm - get bent [2016]/01 sadboy suite (pt.1).mp3
/tmp/jellyfin-favorites-sync/jadeworm - get bent [2016]/02 open house.mp3
/tmp/jellyfin-favorites-sync/jadeworm - get bent [2016]/03 the loop.mp3
/tmp/jellyfin-favorites-sync/jadeworm - rise [2021]/rise.mp3
```

### Scheduling

I recommend setting up a cron task to run the script at a regular interval. For example, to run it every night at 3:00 AM, open your crontab with `crontab -e` and add the line
```
0 3 * * * JFS_USER_ID=... JFS_API_KEY=... JFS_SYNC_FOLDER=/path/to/persistent/directory python3 /path/to/jellyfin-favorites-sync/pull.py
```

### Version Support

This has been tested primarily on Python 3.9 on Linux, but was written with cross-platform support in mind. If you run into any errors, open an issue and I will do my best to help.
