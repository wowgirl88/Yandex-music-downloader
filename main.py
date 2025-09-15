import requests
import json
import os
import sys
import xml.etree.ElementTree as ET
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from configparser import ConfigParser
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TYER, APIC

config = ConfigParser()
config.read("config.conf")
token = config.get("token", "oauth_token")
download_dir = config.get("downloads", "directory")

BANNER = f"""
┓┏┏┓┳┓┳┓┏┓┏┓┏┓  ┳┳┓┳┳┏┓┳┏┓
┗┫┣┫┃┃┃┃┣  ┃┃   ┃┃┃┃┃┗┓┃┃
┗┛┛┗┛┗┻┛┗┛┗┛┗┛  ┛ ┗┗┛┗┛┻┗┛
┳┓┏┓┓ ┏┳┓┓ ┏┓┏┓┳┓┏┓┳┓
┃┃┃┃┃┃┃┃┃┃ ┃┃┣┫┃┃┣ ┣┫
┻┛┗┛┗┻┛┛┗┗┛┗┛┛┗┻┛┗┛┛┗
current token: {token[:5]}...
current directory: {download_dir}

[1] download album
[2] download track
[3] settings
[0] exit"""


class YandexMusicDownloader:
    def __init__(self, oauth_token, download_dir):
        self.oauth_token = oauth_token
        self.download_dir = download_dir
        self.session = self._create_session()

    def _create_session(self):
        session = requests.Session()
        retries = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "Authorization": f"OAuth {self.oauth_token}",
                "User-Agent": "Yandex-Music-API",
                "Accept": "*/*",
                "Connection": "keep-alive",
            }
        )
        return session

    def get_album_info(self, album_id):
        print(f"[+] Getting album info for {album_id}...")
        url = f"https://api.music.yandex.net/albums/{album_id}"
        response = self.session.get(url, timeout=15)

        if response.status_code != 200:
            print(f"Error getting album info: {response.status_code}")
            return None

        data = response.json()
        return data.get("result")

    def get_track_info(self, track_id):
        print(f"[+] Getting track info for {track_id}...")
        url = f"https://api.music.yandex.net/tracks/{track_id}"
        response = self.session.get(url, timeout=15)

        if response.status_code != 200:
            print(f"Error getting track info: {response.status_code}")
            return None

        data = response.json()
        return data.get("result")[0] if data.get("result") else None

    def get_album_tracks(self, album_id):
        print(f"[+] Getting tracks for album {album_id}...")
        url = f"https://api.music.yandex.net/albums/{album_id}/with-tracks"
        response = self.session.get(url, timeout=15)

        if response.status_code != 200:
            print(f"Error getting tracks: {response.status_code}")
            return None

        data = response.json()

        if "result" in data and "volumes" in data["result"]:
            return data["result"]["volumes"][0]
        elif "result" in data and "tracks" in data["result"]:
            return data["result"]["tracks"]
        else:
            print("Could not find tracks in API response")
            return None

    def get_download_url(self, track_id):
        download_url = f"https://api.music.yandex.net/tracks/{track_id}/download-info"
        response = self.session.get(download_url, timeout=15)

        if response.status_code != 200:
            return None, None

        download_info = response.json()

        for info in download_info["result"]:
            if info["codec"] == "mp3" and info["bitrateInKbps"] == 320:
                return info["downloadInfoUrl"], info["codec"]

        if download_info["result"]:
            return (
                download_info["result"][0]["downloadInfoUrl"],
                download_info["result"][0]["codec"],
            )

        return None, None

    def download_cover(self, cover_uri, directory):
        try:
            if cover_uri.startswith("http"):
                cover_url = cover_uri
            else:
                cover_url = f"https://{cover_uri.replace('%%', '1000x1000')}"

            response = self.session.get(
                cover_url,
                timeout=15,
                headers={
                    "Referer": "https://music.yandex.ru/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )

            if response.status_code == 200:
                cover_path = os.path.join(directory, "cover.jpg")
                with open(cover_path, "wb") as f:
                    f.write(response.content)
                print("[+] Downloaded cover")
                return cover_path
            else:
                print(f"[-] Cover download failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error downloading cover: {e}")
        return None

    def add_id3_tags(self, file_path, track_info, album_info=None, cover_path=None):
        try:
            audio = MP3(file_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()

            audio.tags.add(TIT2(encoding=3, text=track_info["title"]))

            artists = [artist["name"] for artist in track_info.get("artists", [])]
            audio.tags.add(TPE1(encoding=3, text=", ".join(artists)))

            if album_info:
                audio.tags.add(
                    TALB(encoding=3, text=album_info.get("title", "Unknown Album"))
                )
                
                if "year" in album_info:
                    audio.tags.add(TYER(encoding=3, text=str(album_info["year"])))
            elif track_info.get("albums"):
                album = track_info["albums"][0]
                audio.tags.add(TALB(encoding=3, text=album.get("title", "Unknown Album")))
                
                if "year" in album:
                    audio.tags.add(TYER(encoding=3, text=str(album["year"])))

            if "trackPosition" in track_info:
                track_num = track_info["trackPosition"].get("index", 0)
                audio.tags.add(TRCK(encoding=3, text=str(track_num)))
            elif "trackIndex" in track_info:
                audio.tags.add(TRCK(encoding=3, text=str(track_info["trackIndex"])))

            if cover_path and os.path.exists(cover_path):
                with open(cover_path, "rb") as cover_file:
                    cover_data = cover_file.read()
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_data,
                    )
                )

            audio.save()
            print(f"    [+] Added metadata to track")
        except Exception as e:
            print(f"    [-] Error adding ID3 tags: {e}")

    def download_track(self, url, codec, file_path):
        try:
            with self.session.get(url, stream=True, timeout=30) as response:
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=1 << 14):
                            if chunk:
                                f.write(chunk)
                    return True
        except Exception as e:
            print(f"Download error: {e}")
        return False

    def process_download(self, track_id, track_info=None, album_info=None, directory=None, filename=None):
        download_info_url, codec = self.get_download_url(track_id)
        if not download_info_url:
            print(f"[-] Could not get download info for track")
            return False

        raw_diu = download_info_url.replace("%%", "/")
        info_url = (
            f"https://{raw_diu.lstrip('/')}"
            if not raw_diu.startswith("http")
            else raw_diu
        )

        try:
            response = self.session.get(info_url, timeout=15)
            if response.status_code != 200:
                print(f"[-] Could not get download URL")
                return False

            root = ET.fromstring(response.text)
            host = root.find("host").text
            path = root.find("path").text
            s = root.find("s").text
            ts = root.find("ts").text

            path_encoded = urllib.parse.quote(path, safe="")
            final_url = f"https://{host}/get-{codec}/{s}/{ts}/{path_encoded}"

            if self.download_track(final_url, codec, filename):
                print(f"    [+] Successfully downloaded: {os.path.basename(filename)}")
                self.add_id3_tags(filename, track_info, album_info, 
                                 os.path.join(directory, "cover.jpg") if directory else None)
                return True
            else:
                print(f"    [-] Failed to download")
                return False

        except Exception as e:
            print(f"    [-] Error processing track: {e}")
            return False

    def process_album(self, album_id):
        album_info = self.get_album_info(album_id)
        if not album_info:
            return False

        album_title = album_info.get("title", "Unknown Album")
        artist_name = album_info.get("artists", [{}])[0].get("name", "Unknown Artist")

        tracks = self.get_album_tracks(album_id)
        if not tracks:
            return False

        safe_artist = "".join(
            c for c in artist_name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_album = "".join(
            c for c in album_title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        album_dir = os.path.join(self.download_dir, f"{safe_artist} - {safe_album}")
        os.makedirs(album_dir, exist_ok=True)

        print(f"[+] Found album: {artist_name} - {album_title}")
        print(f"[+] Found {len(tracks)} tracks. Starting download...")
        
        cover_uri = (
            album_info.get("cover_uri")
            or album_info.get("og_image")
            or (album_info.get("cover") and album_info["cover"].get("uri"))
        )
        cover_path = None
        if cover_uri:
            cover_path = self.download_cover(cover_uri, album_dir)
        else:
            print("[-] No cover available for this album")

        for index, track in enumerate(tracks, 1):
            track_id = track["id"]
            track_title = track["title"]
            file_name = f"{index:02d}. {track_title}.mp3".replace("/", "_")
            file_path = os.path.join(album_dir, file_name)

            print(f"[+] Processing track {index}: {track_title}")
            self.process_download(track_id, track, album_info, album_dir, file_path)

        return True

    def process_track(self, track_id):
        track_info = self.get_track_info(track_id)
        if not track_info:
            return False

        track_title = track_info.get("title", "Unknown Track")
        artists = track_info.get("artists", [])
        artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"

        safe_artist = "".join(
            c for c in artist_name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_title = "".join(
            c for c in track_title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        
        track_dir = os.path.join(self.download_dir, f"{safe_artist}")
        os.makedirs(track_dir, exist_ok=True)

        print(f"[+] Found track: {artist_name} - {track_title}")
        
        cover_uri = track_info.get("cover_uri")
        if not cover_uri and track_info.get("albums"):
            album = track_info["albums"][0]
            cover_uri = album.get("cover_uri") or (album.get("cover") and album["cover"].get("uri"))
            
        if cover_uri:
            self.download_cover(cover_uri, track_dir)
        else:
            print("[-] No cover available for this track")

        file_name = f"{safe_artist} - {safe_title}.mp3".replace("/", "_")
        file_path = os.path.join(track_dir, file_name)

        return self.process_download(track_id, track_info, None, track_dir, file_path)


def settings():
    print("""Enter option:
    [1] change token
    [2] change directory
    [0] return to menu""")
    choice = int(input(">>> "))
    if choice == 0:
        return
    elif choice == 1:
        token = input("Enter token: ")
        config["token"]["oauth_token"] = token
        with open("config.conf", "w") as configfile:
            config.write(configfile)
        print("Token updated successfully!")
    elif choice == 2:
        directory = input("Enter path: ")
        config["downloads"]["directory"] = directory
        with open("config.conf", "w") as configfile:
            config.write(configfile)
        print("Directory updated successfully!")
    else:
        print("wrong choice")

def main():
    while True:
        print(BANNER)
        try:
            downloader = YandexMusicDownloader(
                    oauth_token=token,
                    download_dir=download_dir
            )
            choice = int(input(">>> "))
            if choice == 0:
                sys.exit(0)
            elif choice == 1:
                album_id = input("Enter album ID: ").strip()
                if not album_id:
                    print("Album ID is required!")
                    continue
                downloader.process_album(album_id)
            elif choice == 2:
                track_id = input("Enter track ID: ").strip()
                if not track_id:
                    print("Track ID is required!")
                    continue
                downloader.process_track(track_id)
            elif choice == 3:
                settings()
            else:
                print("wrong choice")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)
        except Exception as e:
            print(f"An error occurred: {e}")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
