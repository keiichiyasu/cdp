import musicbrainzngs
import discid
import logging

class MetadataFetcher:
    def __init__(self, user_agent="CDPlayer/1.0", contact="contact@example.com"):
        musicbrainzngs.set_useragent("CDP", "0.1", contact)
        self.logger = logging.getLogger(__name__)

    def get_disc_id(self, device_path=None):
        """
        指定されたデバイスパスからDiscIDを読み取る。
        macOSの場合、device_pathは通常指定不要（discidが自動検出）。
        特定のドライブを指定する場合は discid.read(device_path) を使う。
        """
        try:
            # macOSではデフォルトデバイスの読み取りを試みる
            # device_pathが渡された場合でも、libdiscidの仕様に合わせて処理が必要
            # discid.read() は通常、最初のドライブを読みに行く
            disc = discid.read()
            return disc.id
        except discid.DiscError as e:
            self.logger.error(f"Error reading disc ID: {e}")
            return None

    def fetch_metadata(self, disc_id):
        """
        DiscIDに基づいてMusicBrainzからメタデータを取得する。
        """
        if not disc_id:
            return None

        try:
            # DiscIDでリリースを検索
            # includes=['artists', 'recordings', 'release-groups'] で必要な情報を一度に取得
            result = musicbrainzngs.get_releases_by_discid(
                disc_id, includes=['artists', 'recordings', 'release-groups']
            )

            if 'disc' in result and 'release-count' in result['disc'] and result['disc']['release-count'] > 0:
                # 複数のリリースが見つかる場合があるが、とりあえず最初のものを採用
                release = result['disc']['release-list'][0]
                return self._parse_release(release)
            else:
                self.logger.warning("No release found for this disc ID.")
                return None

        except musicbrainzngs.WebServiceError as e:
            self.logger.error(f"MusicBrainz API error: {e}")
            return None

    def _parse_release(self, release):
        """
        MusicBrainzのレスポンスから必要な情報を抽出して辞書にまとめる。
        """
        metadata = {
            "title": release.get('title', 'Unknown Album'),
            "id": release.get('id'),
            "artist": "Unknown Artist",
            "tracks": [],
            "cover_art_url": None
        }

        # アーティスト名の取得
        if 'artist-credit' in release:
            metadata['artist'] = release['artist-credit'][0]['artist']['name']

        # トラックリストの取得
        if 'medium-list' in release:
            for medium in release['medium-list']:
                if 'track-list' in medium:
                    for track in medium['track-list']:
                        track_info = {
                            "number": track['number'],
                            "title": track['recording']['title'],
                            "length": track['recording'].get('length') # milliseconds
                        }
                        metadata['tracks'].append(track_info)

        # カバーアートの取得（Cover Art Archive）
        if metadata['id']:
            metadata['cover_art_url'] = self._get_cover_art_url(metadata['id'])

        return metadata

    def _get_cover_art_url(self, release_id):
        """
        Release IDからカバーアートのURLを取得する。
        """
        try:
            # musicbrainzngs には直接Cover Art Archiveを叩く関数がないため、URLを推測または別APIを使う
            # ここでは musicbrainzngs.get_image_list を使う手もあるが、URL構築の方が軽量
            # data = musicbrainzngs.get_image_list(release_id)
            # シンプルにfront画像をリクエストするURL
            return f"https://coverartarchive.org/release/{release_id}/front"
        except Exception as e:
            self.logger.warning(f"Could not fetch cover art URL: {e}")
            return None
