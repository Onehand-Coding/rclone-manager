# Rclone Manager

A powerful Python-based command-line tool that simplifies rclone operations with an intuitive interface for managing file transfers, serving files, and navigating both local and remote storage systems.

## Features

- **🚀 Interactive File Management**: Navigate local and remote directories with an intuitive numbered interface
- **📤 Smart Upload**: Upload files and folders to multiple cloud storage providers with overwrite protection
- **📥 Flexible Download**: Download files from remote storage with selective file picking
- **🌐 Multi-Protocol Server**: Serve files via HTTP, WebDAV, or FTP protocols
- **☁️ Multi-Cloud Support**: Works with Google Drive, Mega, Google Photos, and other rclone-supported providers
- **🔄 Batch Operations**: Handle multiple files and remotes simultaneously
- **⚡ Optimized Performance**: Built-in VFS caching for improved transfer speeds
- **🛡️ Safe Operations**: Overwrite protection and confirmation prompts

## Supported Storage Providers

- **Google Drive** (including shared drives)
- **Mega**
- **Google Photos**
- **And any other rclone-supported backend**

## Prerequisites

- Python 3.8+
- [rclone](https://rclone.org/downloads/) installed and configured
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/rclone-scripts.git
cd rclone-scripts
```

2. Install dependencies:
```bash
uv sync
```

3. Ensure rclone is configured with your cloud storage remotes:
```bash
rclone config
```

## Usage

### Upload Files

Upload local files or folders to remote storage:

```bash
uv run python rclone_manager.py upload [--overwrite]
```

**Interactive Process:**
1. Navigate and select local files/folders
2. Choose destination remote
3. Select remote destination folder
4. Confirm upload

**Options:**
- `--overwrite`: Enable overwrite mode (ignores file timestamps)

### Download Files

Download files from remote storage to local system:

```bash
uv run python rclone_manager.py download [--overwrite]
```

**Interactive Process:**
1. Select source remote
2. Navigate and select remote files/folders
3. Choose local destination folder
4. Confirm download

**Options:**
- `--overwrite`: Enable overwrite mode (ignores file timestamps)

### Serve Local Files

Share local directories over the network:

```bash
uv run python rclone_manager.py serve-local
```

**Interactive Process:**
1. Navigate and select local directory to serve
2. Choose protocol (HTTP, WebDAV, or FTP)
3. Server starts on your local IP address

**Default Settings:**
- **IP**: Your local network IP (auto-detected)
- **Port**: 8080 (HTTP/WebDAV), 8080+ (FTP)
- **Credentials**: Admin/471536 (FTP)

### Serve Remote Files

Serve remote storage over the network:

```bash
uv run python rclone_manager.py serve-remote
```

**Interactive Process:**
1. Select one or more remotes to serve
2. Choose protocol (HTTP, WebDAV, or FTP)
3. Multiple servers start on different ports

**Features:**
- **Multi-remote serving**: Serve multiple cloud storages simultaneously
- **Automatic port allocation**: Each remote gets its own port
- **Shared drive support**: Optional Google Drive shared folders
- **Optimized caching**: VFS cache for better performance

**Default Ports:**
- First remote: 8080
- Additional remotes: 8081, 8082, 8083...

## Configuration

### VFS Cache Settings

The tool uses optimized VFS caching for better performance:

- **Cache Mode**: `full` (downloads files completely before serving)
- **Cache Size**: 1-10GB depending on the remote type
- **Cache Duration**: 24 hours
- **Google Photos**: Enhanced with `--gphotos-read-size` for better compatibility

### Network Settings

- **Auto IP Detection**: Automatically detects your local network IP
- **Default Credentials**: Username: `Admin`, Password: `471536`
- **Multiple Protocols**: HTTP, WebDAV, FTP support

## Navigation Guide

### File Selection Syntax

- **Single item**: `1` (select item 1)
- **Multiple items**: `1,2,3` (select items 1, 2, and 3)
- **Range**: `1-5` (select items 1 through 5)
- **Go up**: `..` (navigate to parent directory)
- **Select current**: `.` or `d` (select current directory/path)

### Directory Navigation

Navigate through both local and remote directories using the numbered interface:

```
Current Directory: /home/user/Downloads
1. 📁 Folder1/
2. 📁 Folder2/
3. 📄 file1.txt
4. 📄 file2.txt
Navigate by number, '..' (up), or select items (e.g., 1 or 2,3). Press '.' or 'd' to select this directory.:
```

## Examples

### Upload a folder to Google Drive
```bash
uv run python rclone_manager.py upload
# Navigate to your folder, select Google Drive remote, choose destination
```

### Download photos from Google Photos
```bash
uv run python rclone_manager.py download --overwrite
# Select Google Photos remote, choose photos, select local destination
```

### Serve multiple cloud storages
```bash
uv run python rclone_manager.py serve-remote
# Select multiple remotes (e.g., 1,2,3), choose FTP protocol
# Access via FTP clients on ports 8080, 8081, 8082
```

### Share local files over HTTP
```bash
uv run python rclone_manager.py serve-local
# Navigate to folder, select HTTP protocol
# Access via browser at http://YOUR_IP:8080
```

## Troubleshooting

### Common Issues

1. **Remote not found**: Ensure rclone is configured with `rclone config`
2. **Permission denied**: Check file permissions and rclone remote access
3. **Network issues**: Verify firewall settings for serving functionality
4. **Cache issues**: Clear rclone cache with `rclone cache clear`

### Performance Tips

- Use `--overwrite` flag carefully to avoid unnecessary transfers
- For large files, the VFS cache will improve serving performance
- Multiple remotes can be served simultaneously for better organization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built on top of [rclone](https://rclone.org/) - the awesome cloud storage sync tool
- Inspired by the need for a more user-friendly rclone interface

---

**Note**: This tool is a wrapper around rclone and requires a properly configured rclone installation. Make sure to secure your credentials and use appropriate network security measures when serving files.
