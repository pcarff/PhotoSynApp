# PhotoSynApp

Automated background pipeline that backs up your Google Photos library to your Synology NAS (or any Docker-capable server) using Google Takeout and Google Drive.

---

## Why this exists (and why it works this way)

On **March 31, 2025**, Google locked down the Google Photos Library API: third-party apps can no longer list or download a user's existing photo library—only media uploaded directly by that specific app. The official replacement (the Google Photos Picker API) requires manual user selection in a web browser for every batch—making automated, headless, scheduled backups impossible via the Photos API.

**Google Takeout is the only remaining path to an automated full-library backup.** 
This application leverages Google Takeout's **recurring scheduled export** feature delivered directly to Google Drive, and polls Google Drive (a standard, unrestricted API) for new export archives.

Because each recurring Takeout export re-exports your entire photo library from scratch, **PhotoSynApp computes a SHA-256 content hash for every file and deduplicates it against an internal SQLite state database**. Repeated exports will never duplicate storage or create duplicate files in your photo library.

---

## Pipeline Overview

```text
[ Google Photos ] ──(Every 2 Months)──> [ Google Takeout ] ──> [ Google Drive /Takeout ]
                                                                       │
                                                                 (Poll & Download)
                                                                       ▼
                                                              [ /staging/raw ]
                                                                       │
                                                                  (Extract)
                                                                       ▼
                                                             [ /staging/extracted ]
                                                                       │
                                                       (gpth EXIF fix & YYYY/MM organize)
                                                                       ▼
                                                             [ /staging/gpth-out ]
                                                                       │
                                                            (SHA-256 Dedup Check)
                                                                       ▼
                                                           [ Final NAS Photo Library ]
```

1. **Polls Google Drive** for Takeout export archives (`takeout-<timestamp>-<part>.zip`).
2. **Groups multi-part archives** (including multi-segment filenames like `takeout-...-1-001.zip`).
3. **Waits for the upload quiet period** (`quiet_period_minutes`) so all zip split parts are fully finished before processing starts.
4. **Downloads and extracts** the zip archives into a local scratch staging area.
5. **Runs [`gpth`](https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo)** to fix corrupted EXIF metadata, parse Google JSON companion sidecars, and organize all photos into a clean `YYYY/MM` folder hierarchy.
6. **Deduplicates & imports** photos into your permanent NAS photo directory, skipping any photo/video whose SHA-256 hash already exists.
7. **Cleans up** staging zips and scratch directories automatically.

---

## Prerequisites

- Synology NAS (or Linux server) with **Docker** & **Docker Compose** installed.
- A Google account with photos to back up.
- Google Cloud project for Google Drive API access.

---

## Step-by-Step Setup Guide

### Step 1: Google Cloud Project Setup (Drive API)

Because PhotoSynApp monitors your Google Drive folder headlessly, it requires OAuth access to read Drive files.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `PhotoSync`).
3. Navigate to **APIs & Services > Library**, search for **Google Drive API**, and click **Enable**.
4. Go to **APIs & Services > OAuth consent screen**:
   - Select **External** and click **Create**.
   - Fill in the required fields (App name: `PhotoSync`, user support email, developer contact).
   - Under **Scopes**, click **Add or Remove Scopes** and select `https://www.googleapis.com/auth/drive.readonly`.
   - Under **Test users**, **add your own Google email address**.
   - Keep publishing status as **"Testing"** (this is free, immediate, and avoids Google's verification process for personal use).
5. Go to **APIs & Services > Credentials**:
   - Click **Create Credentials > OAuth client ID**.
   - Application type: **Desktop app**.
   - Name: `PhotoSync Desktop Client`.
   - Click **Create**, then click **Download JSON** on the created credential.

---

### Step 2: Generate OAuth Token (`token.json`)

Run this one-time command on a computer with a desktop web browser (e.g., your laptop):

```bash
# 1. Install Google Auth library
pip install google-auth-oauthlib

# 2. Run the authorization script
python scripts/authorize.py --client-secret /path/to/downloaded_client_secret.json --out config/token.json
```

A browser window will open. Sign in with your Google account and grant read-only Drive permissions. Once authorized, `token.json` will be saved into your `config/` directory.

---

### Step 3: Schedule Google Takeout Recurring Export

1. Navigate to [takeout.google.com](https://takeout.google.com/).
2. Click **"Deselect all"** at the top.
3. Scroll down and check **Google Photos** only (make sure no other Google services are checked).
4. Click **Next step**.
5. Configure export settings:
   - **Transfer to**: `Add to Drive`
   - **Frequency**: `Export every 2 months for 1 year` (6 exports)
   - **File type & size**: `.zip` with **50 GB** (choose the largest size to minimize split part count).
6. Click **Create export**.

> Google will generate the archive in the background and place it directly into a folder named `Takeout` at the root of your Google Drive.

---

### Step 4: Configure `PhotoSynApp`

1. Copy the example configuration:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

2. Customize [config/config.yaml](config/config.yaml):
   ```yaml
   drive:
     folder_name: "Takeout"
     folder_id: null
     token_path: "/config/token.json"

   poll_interval_minutes: 360  # Check every 6 hours
   quiet_period_minutes: 45    # Ensure Google finished uploading all parts

   staging_dir: "/staging"
   library_dir: "/photos"
   state_db_path: "/state/state.sqlite3"
   ```

3. Update [docker-compose.yml](docker-compose.yml) volume paths:
   ```yaml
   services:
     photosync:
       build: .
       container_name: photosync
       restart: unless-stopped
       environment:
         - CONFIG_PATH=/config/config.yaml
         - LOG_LEVEL=INFO
       volumes:
         - ./config:/config:ro
         - ./state:/state
         - ./staging:/staging
         # Point host path to your destination photos folder on the NAS:
         - /volume1/Photos:/photos
   ```

---

### Step 5: Launch with Docker Compose

Start the container:

```bash
docker compose up -d --build
```

View live logs:

```bash
docker compose logs -f
```

---

## Ingesting Physical Scanned Photos

If you scan vintage or physical family photos, you can ingest them into the library with automatic deduplication hash registration:

```bash
# Ingest into Laura's isolated archive:
python scripts/add_scanned_photo.py /path/to/scan.png --target laura --year 1924 --month 08

# Ingest into Paul's combined archive:
python scripts/add_scanned_photo.py /path/to/scan.png --target paul --year 1931 --month 09
```

This ensures:
1. Files land in the correct `YYYY/MM` folder hierarchy.
2. Permissions are set to `0664` for network sharing.
3. Content SHA-256 hashes are registered in SQLite (`state_laura.sqlite3` or `state.sqlite3`) so future Google Takeout archives will recognize them and avoid duplicate imports.

---

## Storage Sizing Recommendations

Each processed export requires temporary staging space for:
1. Raw zip archives
2. Extracted files
3. `gpth` organized output

At peak, this requires **roughly ~3x your Google Photos library size** during an active extraction run before automatic cleanup. Make sure the volume backing `./staging` has adequate disk space.

---

## Development & Testing

Run unit tests locally:

```bash
pip install -r requirements.txt pytest
pytest
```

---

## License

MIT License. Feel free to modify and adapt for personal or self-hosted backup needs.

