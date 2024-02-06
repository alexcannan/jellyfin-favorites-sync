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
    ProductionYear: str
    IndexNumber: int
    Path: str

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
        file.unlink()


def sync_audio(audio: Audio):
    if not audio.sync_filepath.exists():
        audio.sync_filepath.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"Syncing {audio.Path} to {audio.sync_filepath}")
        rc = subprocess.run([
            "ffmpeg",
            "-i", audio.Path,
            "-codec:a", "libmp3lame",
            "-q:a", "2",
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
