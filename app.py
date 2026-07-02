import os
import sys

# Add Homebrew to PATH on macOS to ensure ffmpeg/ffprobe are found when run as an App bundle
if sys.platform == "darwin":
    for path in ("/opt/homebrew/bin", "/usr/local/bin"):
        if path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = path + os.path.pathsep + os.environ.get("PATH", "")

try:
    sys.stdout.reconfigure(write_through=True, line_buffering=True)
    sys.stderr.reconfigure(write_through=True, line_buffering=True)
except Exception:
    pass

def main():
    import threading
    import time
    import webview
    from gui import main as start_server
    
    class Api:
        def __init__(self):
            self.window = None

        def select_file(self):
            if not self.window:
                return ""
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=('Video files (*.mp4;*.mkv;*.mov;*.avi;*.webm)', 'All files (*.*)')
            )
            return result[0] if result else ""

        def select_folder(self):
            if not self.window:
                return ""
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            return result[0] if result else ""

    def on_closed():
        from gui import active_process
        if active_process:
            try:
                active_process.terminate()
            except Exception:
                pass
        sys.exit(0)

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Wait a bit for server to start
    time.sleep(0.8)
    
    # Instantiate the exposed Javascript API
    api = Api()
    
    # Create webview window
    window = webview.create_window(
        title="Apple Silicon Video Upscaler",
        url="http://127.0.0.1:8080",
        width=900,
        height=750,
        min_size=(800, 650),
        resizable=True,
        js_api=api
    )
    api.window = window
    
    # Register closing callback
    window.events.closed += on_closed
    
    # Start the webview loop
    webview.start()

if __name__ == "__main__":
    if os.environ.get("VIDEO_UPSCALER_CLI") == "1":
        # Run as the CLI upscaler helper
        import upscale
        sys.exit(upscale.main())
    else:
        # Run as the native GUI app
        main()
