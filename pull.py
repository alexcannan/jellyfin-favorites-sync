"""
reads favorited tracks/albums from jellyfin, and syncs them to a specified directory.
transcodes audio files to desired format (mp3 by default).
"""

import concurrent.futures
from dataclasses import dataclass
import inspect
import json
import logging
import logging.handlers
from pathlib import Path
import os
import subprocess
from typing import List, Literal

import requests


### CONFIG / SETUP


config_file = Path(__file__).parent / "config.json"
config = json.loads(config_file.read_text())
SYNC_FOLDER = config["SYNC_FOLDER"]
API_KEY = config["API_KEY"]
SERVER_URL = config["SERVER_URL"]
USER_ID = config["USER_ID"]
assert API_KEY and USER_ID, "set API_KEY and USER_ID in config.json"


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_file = Path(__file__).parent / "jellyfin-favorites-dump.log"
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=5*1024*1024)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(log_formatter)
logger.addHandler(console)

Path(SYNC_FOLDER).mkdir(exist_ok=True, parents=True)

headers = {
    'X-Emby-Token': API_KEY,
}

ffmpeg_bin_response = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
assert not ffmpeg_bin_response.returncode, "ffmpeg not found in PATH"
ffmpeg_bin = ffmpeg_bin_response.stdout.strip()
logger.debug(f"Found ffmpeg at {ffmpeg_bin}")


### VALIDATION


@dataclass
class BaseItem:
    @classmethod
    def from_dict(cls, env):
        return cls(**{
            k: v for k, v in env.items()
            if k in inspect.signature(cls).parameters
        })


@dataclass
class Item(BaseItem):
    Name: str
    Id: str
    Type: Literal["MusicAlbum", "MusicArtist", "Audio"]


@dataclass
class Audio(Item):
    Artists: List[str]
    Album: str
    AlbumId: str
    Path: str
    IndexNumber: int = -1
    ProductionYear: str = "UNK"

    @property
    def artist_repr(self):
        return ", ".join(self.Artists)

    @property
    def extension(self):
        return Path(self.Path).suffix

    @property
    def sync_filepath(self):
        return Path(SYNC_FOLDER) / f"{self.artist_repr} - {self.Album} [{self.ProductionYear}]" / f"{self.IndexNumber:02} {self.Name}.mp3"


### LET'S GO


audio: List[Audio] = []
parent_items: List[Item] = []


# get all favorited audio, including albums and artists
params = {
    "includeItemTypes": ["MusicAlbum", "MusicArtist", "Audio"],
    "recursive": True,
    "isFavorite": True,
    "fields": ["Path"],
}
items_url = f"{SERVER_URL}/Users/{USER_ID}/Items"
favorites_response = requests.get(items_url, headers=headers, params=params)
favorites = favorites_response.json()


for item in favorites["Items"]:
    if item["Type"] == "Audio":
        audio.append(Audio.from_dict(item))
    else:
        parent_items.append(Item.from_dict(item))


# get all audio from favorited albums and artists
logger.info(f"{len(audio)} song(s) favorited, now gathering songs from {len(parent_items)} favorited Artists/Albums")
for parent_item in parent_items:
    params = {
        "includeItemTypes": ["Audio"],
        "recursive": True,
        "parentId": parent_item.Id,
        "fields": ["Path"],
    }
    children_response = requests.get(items_url, headers=headers, params=params)
    children = children_response.json()
    for child in children["Items"]:
        audio.append(Audio.from_dict(child))


audio_sync_paths = {a.sync_filepath.absolute(): a for a in audio}
# delete any files in the sync folder that aren't in the audio list
for file in Path(SYNC_FOLDER).rglob("*"):
    if file.is_file() and file.absolute() not in audio_sync_paths:
        logger.debug(f"Deleting file {file}")
        file.unlink()


def sync_audio(audio: Audio):
    if not audio.sync_filepath.exists():
        audio.sync_filepath.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"Syncing {audio.Path} to {audio.sync_filepath}")
        rc = subprocess.run([
            ffmpeg_bin,
            "-i", audio.Path,
            "-codec:a", "libmp3lame",
            "-q:a", "0",  # V0 quality
            "-ar", "44100",
            "-ac", "2",
            audio.sync_filepath,
        ], capture_output=True)
        if rc.returncode:
            logger.error(f"Failed to sync {audio.Path} to {audio.sync_filepath}")
            logger.error(f"ffmpeg output: {rc.stderr.decode()}")


# sync audio files
n_workers = os.cpu_count() - 1 or 1
audios = list(audio_sync_paths.values())
new_audios = [a for a in audios if not a.sync_filepath.exists()]
logger.info(f"Syncing {len(new_audios)} new audio files from {len(audios)} favorited"
            f" ({100 * len(new_audios) / len(audios):.2f}%)")
# display % completed every 20%
progress_messages = {min(int(0.2 * len(new_audios) * i), len(new_audios)-1): f"{20 * i}%" for i in range(6)}
with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
    n_complete = 0
    futures = {executor.submit(sync_audio, audio): audio for audio in new_audios}
    for _ in concurrent.futures.as_completed(futures):
        if n_complete in progress_messages:
            logger.info(f"{progress_messages[n_complete]} complete")
        n_complete += 1


def sync_cover(album_dir: Path, album_id: str):
    album_cover_url = f"{SERVER_URL}/Items/{album_id}/Images/Primary"
    cover_response = requests.get(album_cover_url, headers=headers)
    if cover_response.headers["Content-Type"] == "image/jpeg":
        ext = "jpg"
    elif cover_response.headers["Content-Type"] == "image/png":
        ext = "png"
    else:
        logger.error(f"Unknown cover image type: {cover_response.headers['Content-Type']}")
        return
    cover_path = album_dir / f"cover.{ext}"
    if not cover_path.exists():
        with open(cover_path, "wb") as f:
            f.write(cover_response.content)
            logger.debug(f"Synced cover for {album_dir}")


if True:
    # sync album art
    album_dirs_to_id = {a.sync_filepath.parent: a.AlbumId for a in audio}
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
        album_futures = {}
        for album_dir, album_id in album_dirs_to_id.items():
            album_futures[executor.submit(sync_cover, album_dir, album_id)] = album_dir
        for _ in concurrent.futures.as_completed(futures):
            pass
