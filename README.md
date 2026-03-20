# Rclone Manager

A powerful Python CLI tool that simplifies rclone operations with an intuitive interface for managing file transfers, mounting cloud storage, serving files, and automating sync tasks.

## Features

- **📤 Upload/Download**: Interactive file transfers with overwrite protection
- **🔗 Mount Remotes**: Mount cloud storage as local directories with FUSE
- **🌐 Serve Files**: Share local/remote files via HTTP, WebDAV, or FTP
- **🔄 Sync Pairs**: Automate recurring sync tasks with configurable modes
- **☁️ Multi-Cloud**: Support for Google Drive, Mega, Google Photos, and all rclone backends
- **📊 Status Dashboard**: View active mounts and sync pairs at a glance
- **🛠️ Storage Utils**: Checksum verification, deduplication, space usage, copy-between remotes
- **🖥️ Web UI**: Browser-based interface for file management

## Supported Storage Providers

- **Google Drive** (including shared drives)
- **Mega**
- **Google Photos**
- **Any rclone-supported backend** (S3, Dropbox, OneDrive, etc.)

## Prerequisites

- Python 3.8+
- [rclone](https://rclone.org/downloads/) installed and configured
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Onehand-Coding/rclone-manager.git
cd rclone-manager
```

2. **Install dependencies:**
```bash
uv sync
```

3. **Configure rclone remotes:**
```bash
rclone config
```

4. **Generate default config (optional):**
```bash
uv run rclone-manager generate-config
```
This creates `configs/config.ini` with example settings. Edit it to customize credentials and rclone flags.

## Configuration

All configuration files live in the `configs/` directory:

```
rclone-manager/
├── configs/
│   ├── config.ini           # Main configuration (create from .example)
│   ├── config.ini.example   # Template with defaults
│   └── sync-pairs.json      # Automated sync pair definitions
```

### config.ini

Contains:
- **DEFAULT section**: Log level, port, username/password for serving
- **rclone_flags section**: Custom flags per remote type (mega, drive, google photos)

### sync-pairs.json

Defines automated sync tasks with modes like upload-only, download-only, sync, and two-way bisync.

## Usage

### Core Commands

#### Upload Files
```bash
uv run rclone-manager upload [--overwrite]
```
Interactive upload with file/folder selection and remote destination choice.

#### Download Files
```bash
uv run rclone-manager download [--overwrite]
```
Interactive download from remote storage.

#### Sync Between Remotes
```bash
uv run rclone-manager sync
```
Direct sync between two remote storages (no local download).

### Mount & Serve

#### Mount Remote
```bash
uv run rclone-manager mount
```
Mount a remote as a local directory (FUSE).

#### Unmount
```bash
uv run rclone-manager unmount
```
Unmount active rclone mounts.

#### Serve Remote
```bash
uv run rclone-manager serve-remote
```
Serve remote storage over HTTP, WebDAV, or FTP.

#### Serve Local
```bash
uv run rclone-manager serve-local
```
Serve local directories over the network.

### Automation

#### Sync Pairs
```bash
# Interactive menu
uv run rclone-manager sync-pairs

# Direct actions
uv run rclone-manager sync-pairs add
uv run rclone-manager sync-pairs list
uv run rclone-manager sync-pairs run
uv run rclone-manager sync-pairs remove
```

**Sync Modes:**
- `upload_only`: Copy local → remote (safe, no deletions)
- `download_only`: Copy remote → local (safe, no deletions)
- `upload_delete`: Sync local → remote (deletes extra remote files)
- `download_delete`: Sync remote → local (deletes extra local files)
- `two_way`: Bidirectional sync using rclone bisync

#### Status
```bash
uv run rclone-manager status
```
Show active mounts with transfer stats and configured sync pairs.

### Utilities

#### Browse Remote
```bash
uv run rclone-manager ls
```
Navigate and list remote directory contents.

#### Checksum Verification
```bash
uv run rclone-manager checksum
```
Verify file integrity between local and remote.

#### Deduplicate
```bash
uv run rclone-manager dedupe
```
Find and remove duplicate files on a remote.

#### Space Usage
```bash
uv run rclone-manager space
```
Show quota and storage usage for remotes.

#### Copy Between Remotes
```bash
uv run rclone-manager copy-between
```
Copy files directly between two remotes.

#### Two-Way Sync (bisync)
```bash
uv run rclone-manager bisync
```
Bidirectional sync between two remotes.

### Web UI
```bash
uv run rclone-manager web-ui
```
Launch browser-based file manager.

### Configuration Management
```bash
uv run rclone-manager config
```
Manage rclone flags in config.ini interactively.

## Navigation Guide

### File Selection Syntax

- **Single item**: `1` (select item 1)
- **Multiple items**: `1,2,3` (select items 1, 2, and 3)
- **Range**: `1-5` (select items 1 through 5)
- **Go up**: `..` (navigate to parent directory)
- **Select current**: `.` or `d` (select current directory/path)

## Examples

### Upload a folder to Google Drive
```bash
uv run rclone-manager upload
# Navigate to your folder, select Google Drive remote, choose destination
```

### Mount Google Drive as local directory
```bash
uv run rclone-manager mount
# Select remote, choose mount point, access via ~/mnt/<name>
```

### Set up automated sync pair
```bash
uv run rclone-manager sync-pairs add
# Name: "Work Docs"
# Local: /home/user/Documents/Work
# Remote: drive:Backup/Work
# Mode: upload_only
# Run anytime with: uv run rclone-manager sync-pairs run
```

### Check status of mounts and syncs
```bash
uv run rclone-manager status
```

## Troubleshooting

### Common Issues

1. **Remote not found**: Run `rclone config` to set up remotes
2. **Mount fails**: Ensure FUSE is installed (`sudo apt install fuse` on Linux)
3. **Permission denied**: Check file permissions and rclone remote access
4. **Network issues**: Verify firewall settings for serving functionality

### Performance Tips

- Use VFS cache mode for better streaming performance
- Adjust cache size based on available disk space
- Use `--overwrite` flag carefully to avoid unnecessary transfers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built on top of [rclone](https://rclone.org/)
- Uses [Rich](https://github.com/Textualize/rich) for terminal UI

---

**Note**: This tool requires a properly configured rclone installation. Secure your credentials and use appropriate network security when serving files.
