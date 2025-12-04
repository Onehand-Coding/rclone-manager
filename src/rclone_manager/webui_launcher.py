import streamlit as st
import os
import time
from io import BytesIO
from zipfile import ZipFile
import tempfile


def init_session_state():
    """Initialize session state variables"""
    if 'current_path' not in st.session_state:
        st.session_state.current_path = os.path.expanduser("~")
    if 'selected_files' not in st.session_state:
        st.session_state.selected_files = []


def list_directory_contents(path):
    """List contents of a local directory"""
    try:
        contents = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            size = "-" if is_dir else f"{os.path.getsize(item_path)} bytes"
            contents.append({
                "name": item,
                "is_dir": is_dir,
                "size": size,
                "modified": time.ctime(os.path.getmtime(item_path))
            })
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

    st.title("[FOLDER] Rclone Manager Web UI")

    # Sidebar for navigation and options
    with st.sidebar:
        st.header("Options")

        # Authentication (simplified)
        username = st.text_input("Username", value=os.environ.get("USERNAME", ""))
        password = st.text_input("Password", type="password", value=os.environ.get("PASSWORD", ""))

        if username and password:
            st.success("Authenticated")
        else:
            st.info("Credentials from config.ini will be used")

    # Main content area
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("Local File Browser")

        # Show current path
        st.text(f"Current: {st.session_state.current_path}")

        # Refresh button
        if st.button("[REFRESH] Refresh"):
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
                is_selected = st.checkbox("Select", key=checkbox_key, label_visibility="collapsed")

                if is_selected:
                    item_path = os.path.join(st.session_state.current_path, item['name'])
                    if item_path not in st.session_state.selected_files:
                        st.session_state.selected_files.append(item_path)
                else:
                    item_path = os.path.join(st.session_state.current_path, item['name'])
                    if item_path in st.session_state.selected_files:
                        st.session_state.selected_files.remove(item_path)

            with cols[1]:
                if item['is_dir']:
                    if st.button(f"[FOLDER] {item['name']}", key=f"dir_{item['name']}", use_container_width=True):
                        st.session_state.current_path = os.path.join(st.session_state.current_path, item['name'])
                        st.rerun()
                else:
                    st.write(f"[FILE] {item['name']}")

            with cols[2]:
                st.write(item['size'])

            with cols[3]:
                st.write(item['modified'])

    # Navigation controls
    if st.session_state.current_path != os.path.expanduser("~"):
        if st.button("[FOLDER] Go Up"):
            st.session_state.current_path = os.path.dirname(st.session_state.current_path)
            st.rerun()

    # Bulk operations
    with col2:
        st.subheader("Bulk Operations")

        st.write(f"Selected: {len(st.session_state.selected_files)} items")

        if st.button("[ZIP] Download Selected as ZIP", disabled=len(st.session_state.selected_files) == 0):
            with st.spinner("Creating ZIP file..."):
                zip_buffer = download_files_as_zip(st.session_state.selected_files)

                if zip_buffer:
                    st.download_button(
                        label="[DOWNLOAD] Download ZIP",
                        data=zip_buffer,
                        file_name="selected_files.zip",
                        mime="application/zip"
                    )

        # Clear selection button
        if st.button("[CLEAR] Clear Selection"):
            st.session_state.selected_files = []
            st.rerun()

        # Upload functionality
        st.subheader("Upload")
        uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True)

        if uploaded_files:
            if st.button("Upload Files"):
                with st.spinner("Uploading files..."):
                    try:
                        for uploaded_file in uploaded_files:
                            # Upload to destination
                            dest_path = os.path.join(st.session_state.current_path, uploaded_file.name)
                            with open(dest_path, "wb") as f:
                                f.write(uploaded_file.getvalue())

                        st.success(f"Uploaded {len(uploaded_files)} file(s) successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {str(e)}")


if __name__ == "__main__":
    main_app()