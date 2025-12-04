def main():
    """Main entry point when called from CLI - starts Streamlit server programmatically"""
    import subprocess
    import sys
    import os
    import socket

    # Get local IP address
    def get_local_ip():
        try:
            # Connect to a remote address (doesn't actually send data)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    local_ip = get_local_ip()

    # Path to the web UI launcher script
    import pathlib
    current_dir = pathlib.Path(__file__).parent
    launcher_path = current_dir / 'webui_launcher.py'

    # Command to run streamlit with the web UI script
    cmd = [sys.executable, "-m", "streamlit", "run", str(launcher_path),
           "--server.address=0.0.0.0",  # Allow external connections
           "--server.port=8501",        # Default port
           "--server.enableCORS=false", # Handle CORS properly
           "--server.enableXsrfProtection=false"]

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