import streamlit as st
import os
import time
import subprocess
from io import BytesIO
from zipfile import ZipFile
import tempfile


def init_session_state():
    """Initialize session state variables"""
    if "current_path" not in st.session_state:
        st.session_state.current_path = os.path.expanduser("~")
    if "selected_files" not in st.session_state:
        st.session_state.selected_files = []
    if "show_hidden" not in st.session_state:
        st.session_state.show_hidden = False
    if "current_remote" not in st.session_state:
        st.session_state.current_remote = None
    if "remote_path" not in st.session_state:
        st.session_state.remote_path = None


def list_rclone_remotes() -> list:
    """
    Returns a list of all rclone remotes, filtering out remotes ending in '-shared'.
    """
    try:
        output = subprocess.check_output(["rclone", "listremotes"]).decode("utf-8")
        remotes = [line.strip().replace(":", "") for line in output.strip().split("\n")]
        # Filter out the shared remotes to avoid duplicates in the list
        return [r for r in remotes if not r.endswith("-shared")]
    except FileNotFoundError:
        st.error("rclone not found. Please install it.")
        return []


def list_remote_directory_contents(remote_path):
    """List contents of a remote directory"""
    try:
        # Use rclone lsf to list files/directories with trailing slash for directories
        output = subprocess.check_output(
            ["rclone", "lsf", "--dirs-only", remote_path]
        ).decode("utf-8")
        dirs = [item.strip() for item in output.strip().split("\n") if item.strip()]

        output = subprocess.check_output(
            ["rclone", "lsf", "--files-only", remote_path]
        ).decode("utf-8")
        files = [item.strip() for item in output.strip().split("\n") if item.strip()]

        contents = []

        # Add directories
        for item in dirs:
            if not st.session_state.show_hidden and item.startswith("."):
                continue
            contents.append(
                {
                    "name": item.rstrip("/"),  # Remove trailing slash
                    "is_dir": True,
                    "size": "-",
                    "modified": "-",
                }
            )

        # Add files
        for item in files:
            if not st.session_state.show_hidden and item.startswith("."):
                continue
            # Get file size - this will be slower but more accurate
            try:
                size_output = subprocess.check_output(
                    ["rclone", "ls", "--max-depth", "1", f"{remote_path}{item}"]
                ).decode("utf-8")
                size = size_output.split()[0] + " bytes" if size_output.split() else "-"
            except:
                size = "-"

            contents.append(
                {"name": item, "is_dir": False, "size": size, "modified": "-"}
            )

        return sorted(contents, key=lambda x: (not x["is_dir"], x["name"]))
    except subprocess.CalledProcessError as e:
        st.error(f"Error accessing remote path: {remote_path}")
        return []


def list_directory_contents(path):
    """List contents of a local directory"""
    try:
        contents = []
        for item in os.listdir(path):
            # Skip hidden files unless show_hidden is True
            if not st.session_state.show_hidden and item.startswith("."):
                continue
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            size = "-" if is_dir else f"{os.path.getsize(item_path)} bytes"
            contents.append(
                {
                    "name": item,
                    "is_dir": is_dir,
                    "size": size,
                    "modified": time.ctime(os.path.getmtime(item_path)),
                }
            )
        return sorted(contents, key=lambda x: (not x["is_dir"], x["name"]))
    except PermissionError:
        st.error(f"Permission denied accessing: {path}")
        return []


def download_files_as_zip(file_paths):
    """Download multiple files as a ZIP archive"""
    try:
        if not file_paths:
            st.warning("No files selected for download")
            return None

        # Create a temporary directory to store files
        with tempfile.TemporaryDirectory() as temp_dir:
            for file_path in file_paths:
                # Copy local file to temp directory
                filename = os.path.basename(file_path)
                local_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    import shutil

                    shutil.copy2(file_path, local_path)
                else:
                    # Copy directory
                    dest_dir = os.path.join(temp_dir, filename)
                    import shutil

                    shutil.copytree(file_path, dest_dir)

            # Create ZIP file in memory
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, "w") as zip_file:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Get the relative path from temp_dir to maintain folder structure
                        rel_path = os.path.relpath(file_path, temp_dir)
                        zip_file.write(file_path, rel_path)

            zip_buffer.seek(0)
            return zip_buffer

    except Exception as e:
        st.error(f"Error creating ZIP: {str(e)}")
        return None


def main_app():
    """Main Streamlit application"""
    st.set_page_config(page_title="Rclone Manager Web UI", layout="wide")
    init_session_state()

    st.title("📂 Rclone Manager Web UI")

    # Sidebar for navigation and options
    with st.sidebar:
        st.header("⚙️ Options")

        # Authentication system
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False

        if not st.session_state.authenticated:
            st.subheader("🔐 Login")
            username = st.text_input("Username", value=os.environ.get("USERNAME", ""))
            password = st.text_input(
                "Password", type="password", value=os.environ.get("PASSWORD", "")
            )

            # Check credentials from environment or a predefined set
            correct_username = os.environ.get(
                "WEBUI_USERNAME", os.environ.get("USERNAME", "admin")
            )
            correct_password = os.environ.get(
                "WEBUI_PASSWORD", os.environ.get("PASSWORD", "rclone")
            )

            if st.button("Login"):
                if username == correct_username and password == correct_password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect username or password")
        else:
            st.subheader("🔓 Logged In")
            st.success(f"Welcome, {os.environ.get('USERNAME', 'User')}!")
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.rerun()

            # Remote selection dropdown
            remotes = list_rclone_remotes()
            if remotes:
                # Add an option to switch to local file system
                remote_options = ["Local File System"] + remotes
                selected_option = st.selectbox(
                    "Select Location",
                    remote_options,
                    index=0
                    if st.session_state.current_remote is None
                    else remote_options.index(st.session_state.current_remote)
                    if st.session_state.current_remote in remote_options
                    else 0,
                )

                if selected_option == "Local File System":
                    st.session_state.current_remote = None
                    st.session_state.remote_path = None
                else:
                    if st.session_state.current_remote != selected_option:
                        st.session_state.current_remote = selected_option
                        st.session_state.remote_path = f"{selected_option}:"
            else:
                st.info(
                    "No rclone remotes found. Configure rclone remotes to access cloud storage."
                )

    # Main content area
    col1, col2 = st.columns([3, 1])

    with col1:
        # Check if we're browsing remote or local
        if st.session_state.current_remote:
            st.subheader(f"☁️ Remote: {st.session_state.current_remote}")

            # Show current remote path
            current_display_path = (
                st.session_state.remote_path
                if st.session_state.remote_path
                else f"{st.session_state.current_remote}:"
            )
            st.text(f"Current: {current_display_path}")

            # Toggle for showing hidden files
            st.session_state.show_hidden = st.toggle(
                "Show hidden files", value=st.session_state.show_hidden
            )

            # Refresh button
            if st.button("🔄 Refresh"):
                st.rerun()

            # List and display remote directory contents
            contents = list_remote_directory_contents(
                st.session_state.remote_path or f"{st.session_state.current_remote}:"
            )
        else:
            st.subheader("🏠 Local File Browser")

            # Show current path
            st.text(f"Current: {st.session_state.current_path}")

            # Toggle for showing hidden files
            st.session_state.show_hidden = st.toggle(
                "Show hidden files", value=st.session_state.show_hidden
            )

            # Refresh button
            if st.button("🔄 Refresh"):
                st.rerun()

            # List and display directory contents
            contents = list_directory_contents(st.session_state.current_path)

    # Create table for file listing
    if contents:
        # Add header
        header_cols = st.columns([0.05, 0.5, 0.2, 0.2])
        with header_cols[0]:
            st.write("**Select**")
        with header_cols[1]:
            st.write("**Name**")
        with header_cols[2]:
            st.write("**Size**")
        with header_cols[3]:
            st.write("**Modified**")

        # Add files to the table
        for item in contents:
            cols = st.columns([0.05, 0.5, 0.2, 0.2])

            with cols[0]:
                # Create a unique key for the checkbox
                checkbox_key = f"select_{item['name']}_{hash(item['name'])}"
                is_selected = st.checkbox(
                    "Select", key=checkbox_key, label_visibility="collapsed"
                )

                if is_selected:
                    # Add the full path to the selected files
                    if st.session_state.current_remote:
                        item_path = (
                            f"{st.session_state.remote_path.rstrip('/')}/{item['name']}"
                            if st.session_state.remote_path
                            else f"{st.session_state.current_remote}:{item['name']}"
                        )
                    else:
                        item_path = os.path.join(
                            st.session_state.current_path, item["name"]
                        )

                    if item_path not in st.session_state.selected_files:
                        st.session_state.selected_files.append(item_path)
                else:
                    # Remove the full path from selected files
                    if st.session_state.current_remote:
                        item_path = (
                            f"{st.session_state.remote_path.rstrip('/')}/{item['name']}"
                            if st.session_state.remote_path
                            else f"{st.session_state.current_remote}:{item['name']}"
                        )
                    else:
                        item_path = os.path.join(
                            st.session_state.current_path, item["name"]
                        )

                    if item_path in st.session_state.selected_files:
                        st.session_state.selected_files.remove(item_path)

            with cols[1]:
                # Determine the appropriate icon based on file type
                if item["is_dir"]:
                    icon = "📁"
                    if st.button(
                        f"{icon} {item['name']}",
                        key=f"dir_{item['name']}",
                        use_container_width=True,
                    ):
                        if st.session_state.current_remote:
                            # Update remote path
                            new_path = (
                                f"{st.session_state.remote_path.rstrip('/')}/{item['name']}/"
                                if st.session_state.remote_path
                                else f"{st.session_state.current_remote}:{item['name']}/"
                            )
                            st.session_state.remote_path = new_path
                        else:
                            # Update local path
                            st.session_state.current_path = os.path.join(
                                st.session_state.current_path, item["name"]
                            )
                        st.rerun()
                else:
                    # Determine file type based on extension
                    file_ext = os.path.splitext(item["name"])[1].lower()
                    if file_ext in [
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".gif",
                        ".bmp",
                        ".svg",
                        ".webp",
                    ]:
                        icon = "🖼️"  # Image file
                    elif file_ext in [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"]:
                        icon = "🎬"  # Video file
                    elif file_ext in [".mp3", ".wav", ".flac", ".aac", ".ogg"]:
                        icon = "🎵"  # Audio file
                    elif file_ext in [".pdf"]:
                        icon = "📄"  # PDF document
                    elif file_ext in [".doc", ".docx"]:
                        icon = "📝"  # Word document
                    elif file_ext in [".xls", ".xlsx"]:
                        icon = "📊"  # Excel spreadsheet
                    elif file_ext in [".ppt", ".pptx"]:
                        icon = "📈"  # PowerPoint presentation
                    elif file_ext in [".txt", ".md", ".rtf"]:
                        icon = "📑"  # Text document
                    elif file_ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
                        icon = "📦"  # Archive file
                    elif file_ext in [
                        ".py",
                        ".js",
                        ".ts",
                        ".html",
                        ".css",
                        ".json",
                        ".xml",
                    ]:
                        icon = "💻"  # Code file
                    else:
                        icon = "📄"  # Default document/file icon
                    st.write(f"{icon} {item['name']}")

            with cols[2]:
                st.write(item["size"])

            with cols[3]:
                st.write(item["modified"])

    # Navigation controls - different for remote vs local
    if st.session_state.current_remote:
        # Remote navigation controls
        current_remote_path = (
            st.session_state.remote_path or f"{st.session_state.current_remote}:"
        )
        if current_remote_path.strip(
            "/"
        ) != f"{st.session_state.current_remote}:".strip("/"):
            if st.button("📁 Go Up"):
                # Navigate up in remote path
                parent_path = (
                    "/".join(current_remote_path.rstrip("/").split("/")[:-1]) + "/"
                )
                if parent_path == "/":  # Handle root case
                    parent_path = f"{st.session_state.current_remote}:"
                st.session_state.remote_path = parent_path
                st.rerun()
    else:
        # Local navigation controls
        if st.session_state.current_path != os.path.expanduser("~"):
            if st.button("📁 Go Up"):
                st.session_state.current_path = os.path.dirname(
                    st.session_state.current_path
                )
                st.rerun()

    # Bulk operations
    with col2:
        st.subheader("📦 Bulk Operations")

        st.write(f"Selected: {len(st.session_state.selected_files)} items")

        # Only show ZIP download for local files for now
        if not st.session_state.current_remote:
            if st.button(
                "📦 Download Selected as ZIP",
                disabled=len(st.session_state.selected_files) == 0,
            ):
                with st.spinner("Creating ZIP file..."):
                    zip_buffer = download_files_as_zip(st.session_state.selected_files)

                    if zip_buffer:
                        st.download_button(
                            label="📥 Download ZIP",
                            data=zip_buffer,
                            file_name="selected_files.zip",
                            mime="application/zip",
                        )

        # Clear selection button
        if st.button("❌ Clear Selection"):
            st.session_state.selected_files = []
            st.rerun()

        # Upload functionality - only for local files for now
        if not st.session_state.current_remote:
            st.subheader("📤 Upload")
            uploaded_files = st.file_uploader(
                "Choose files", accept_multiple_files=True
            )

            if uploaded_files:
                if st.button("📤 Upload Files"):
                    with st.spinner("Uploading files..."):
                        try:
                            for uploaded_file in uploaded_files:
                                # Upload to destination
                                dest_path = os.path.join(
                                    st.session_state.current_path, uploaded_file.name
                                )
                                with open(dest_path, "wb") as f:
                                    f.write(uploaded_file.getvalue())

                            st.success(
                                f"Uploaded {len(uploaded_files)} file(s) successfully!"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Upload failed: {str(e)}")
        else:
            # For remote, we can add download functionality later
            st.subheader("📥 Remote Operations")
            st.info("Download selected files from remote to local")
            if st.button(
                "📥 Download Selected from Remote",
                disabled=len(st.session_state.selected_files) == 0,
            ):
                st.warning("Remote download functionality coming soon!")


if __name__ == "__main__":
    main_app()
