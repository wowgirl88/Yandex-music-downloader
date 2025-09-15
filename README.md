# Yandex Music Downloader

A Python-based tool for downloading albums and tracks from Yandex Music with metadata preservation.

## Features

- Download entire albums or individual tracks
- Preserve audio quality (up to 320kbps MP3)
- Automatic ID3 tag embedding (title, artist, album, track number, year)
- Album cover art download and embedding
- Configurable download directory
- OAuth token authentication

## Requirements

- Python 3.6+
- Valid Yandex Music account with Yandex Plus subscription
- OAuth token from Yandex Music API

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd yandex-music-downloader
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Obtain your OAuth token:
   - Visit: https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d
   - Log in to your Yandex account
   - Copy the token from the URL after authorization

2. Edit the `config.conf` file:
```ini
[token]
oauth_token = your_oauth_token_here

[downloads]
directory = /path/to/download/directory
```

## Usage

Run the application:
```bash
python main.py
```

Menu options:
- `1` Download album - Enter album ID
- `2` Download track - Enter track ID
- `3` Settings - Configure token and download directory
- `0` Exit - Close the application

## Finding IDs

- Album ID: Found in URL: `https://music.yandex.ru/album/ALBUM_ID`
- Track ID: Found in URL: `https://music.yandex.ru/album/ALBUM_ID/track/TRACK_ID`

## Legal Notice

This tool is intended for personal use only. Please respect copyright laws and Yandex Music's terms of service. Downloading content may violate terms of service in your region.

## Support

For issues and questions, please check:
- Ensure you have an active Yandex Plus subscription
- Verify your OAuth token is valid
- Check your internet connection
- Confirm sufficient storage space in download directory
