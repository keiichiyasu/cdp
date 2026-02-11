import musicbrainzngs
import discid
import logging
import subprocess
import sys
import time
import os

class MetadataFetcher:
    def __init__(self, user_agent="CDPlayer/1.0", contact="contact@example.com"):
        musicbrainzngs.set_useragent("CDP", "0.1", contact)
        self.logger = logging.getLogger(__name__)

    def _get_device_node(self, mount_path):
        try:
            result = subprocess.check_output(["mount"]).decode()
            for line in result.splitlines():
                if mount_path in line:
                    node = line.split()[0]
                    return node.replace("/dev/disk", "/dev/rdisk")
        except: pass
        return None

    def get_disc_id(self, device_path=None):
        target = device_path
        if sys.platform == "darwin" and device_path and device_path.startswith("/Volumes"):
            target = self._get_device_node(device_path)
            self.logger.info(f"Resolved {device_path} to raw device {target}")

        for i in range(3):
            try:
                if target:
                    self.logger.info(f"Reading disc ID (Attempt {i+1}): {target}")
                    disc = discid.read(target)
                else:
                    self.logger.info(f"Reading disc ID (Attempt {i+1}) from default device")
                    disc = discid.read()
                
                self.logger.info(f"Obtained DiscID: {disc.id}")
                return disc.id
            except discid.DiscError as e:
                self.logger.warning(f"DiscID read attempt {i+1} failed: {e}")
                if i == 1: target = None
                time.sleep(2)
        return None

    def fetch_metadata(self, disc_id, fallback_title=None):
        """
        DiscIDで検索し、見つからない場合はタイトルでのフォールバック検索を行う。
        """
        if not disc_id: 
            if fallback_title: return self.search_by_title(fallback_title)
            return None

        try:
            self.logger.info(f"Fetching metadata for DiscID: {disc_id}")
            result = musicbrainzngs.get_releases_by_discid(
                disc_id, includes=['artists', 'recordings', 'release-groups']
            )
            if 'disc' in result and 'release-list' in result['disc']:
                release = result['disc']['release-list'][0]
                return self._parse_release(release)
        except musicbrainzngs.WebServiceError as e:
            self.logger.warning(f"DiscID not found in MusicBrainz (404). Falling back to title search: {fallback_title}")
            if fallback_title:
                return self.search_by_title(fallback_title)
        except Exception as e:
            self.logger.error(f"MusicBrainz API error: {e}")
        
        return None

    def search_by_title(self, title):
        """アルバム名によるベストエフォート検索"""
        if not title or title == "Audio CD": return None
        try:
            self.logger.info(f"Searching MusicBrainz for title: {title}")
            result = musicbrainzngs.search_releases(release=title, limit=1)
            if result['release-list']:
                release_id = result['release-list'][0]['id']
                # 詳細情報を再取得
                full_release = musicbrainzngs.get_release_by_id(release_id, includes=['artists', 'recordings'])
                return self._parse_release(full_release['release'])
        except Exception as e:
            self.logger.error(f"Title search failed: {e}")
        return None

    def _parse_release(self, release):
        metadata = {
            "title": release.get('title', 'Unknown Album'),
            "id": release.get('id'),
            "artist": "Unknown Artist",
            "tracks": [],
            "cover_art_url": None
        }
        if 'artist-credit' in release:
            metadata['artist'] = release['artist-credit'][0]['artist']['name']
        
        # トラックリストのパース (medium-list または直接 track-list)
        tracks = []
        if 'medium-list' in release:
            for medium in release['medium-list']:
                if 'track-list' in medium:
                    tracks.extend(medium['track-list'])
        elif 'track-list' in release:
            tracks = release['track-list']

        for track in tracks:
            track_info = {
                "number": track.get('number', '?'),
                "title": track.get('recording', {}).get('title', 'Unknown Track'),
                "length": track.get('recording', {}).get('length')
            }
            metadata['tracks'].append(track_info)

        if metadata['id']:
            metadata['cover_art_url'] = f"https://coverartarchive.org/release/{metadata['id']}/front"
        
        return metadata
