import subprocess
import sys
import os
import socket
from pathlib import Path

from .utils import get_ip_address


def main():
    """Main entry point when called from CLI - starts Streamlit server programmatically"""
    local_ip = get_ip_address()

    # Path to the web UI launcher script
    current_dir = Path(__file__).parent
    webui_path = current_dir / 'webui.py'

    # Command to run streamlit with the web UI script
    cmd = [sys.executable, "-m", "streamlit", "run", str(webui_path),
           "--server.address=0.0.0.0",  # Allow external connections
           "--server.port=8501",        # Default port
           "--server.enableCORS=false", # Handle CORS properly
           "--server.enableXsrfProtection=false",
           "--server.headless=true"]    # Don't open browser automatically

    # Add the current directory to Python path so imports work correctly
    env = os.environ.copy()
    current_path = os.path.dirname(os.path.dirname(__file__))  # rclone_manager parent directory
    if 'PYTHONPATH' in env:
        env['PYTHONPATH'] = current_path + os.pathsep + env['PYTHONPATH']
    else:
        env['PYTHONPATH'] = current_path

    print("Starting Rclone Manager Web UI...")
    print(f"Access the interface at: http://localhost:8501")
    print(f"On other devices, use: http://{local_ip}:8501")
    print("Press Ctrl+C to stop the server.\n")

    try:
        # Run the Streamlit app
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")
