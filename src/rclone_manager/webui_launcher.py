import subprocess
import sys
import os
from pathlib import Path

from .utils import get_ip_address


def main():
    """Main entry point when called from CLI - starts Streamlit server programmatically"""
    local_ip = get_ip_address()
    bind_addr = os.environ.get("BIND_ADDRESS", "127.0.0.1")
    enable_xsrf = os.environ.get("ENABLE_XSRF_PROTECTION", "true").lower() == "true"
    enable_cors = os.environ.get("ENABLE_CORS", "true").lower() == "true"

    # Path to the web UI launcher script
    current_dir = Path(__file__).parent
    webui_path = current_dir / "webui.py"

    # Command to run streamlit with the web UI script
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(webui_path),
        f"--server.address={bind_addr}",
        "--server.port=8501",
    ]
    if not enable_xsrf:
        cmd.append("--server.enableXsrfProtection=false")
    if not enable_cors:
        cmd.append("--server.enableCORS=false")
    cmd.append("--server.headless=true")

    # Add the current directory to Python path so imports work correctly
    env = os.environ.copy()
    current_path = os.path.dirname(
        os.path.dirname(__file__)
    )  # rclone_manager parent directory
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = current_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = current_path

    print("Starting Rclone Manager Web UI...")
    print("Access the interface at: http://localhost:8501")
    if bind_addr == "0.0.0.0":
        print(f"On other devices, use: http://{local_ip}:8501")
    print("Press Ctrl+C to stop the server.\n")

    try:
        # Run the Streamlit app
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")
