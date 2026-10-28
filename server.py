import json
import subprocess
import os
import sys
import threading
import base64
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import security_utils

# Local only by default; set HOST=0.0.0.0 to accept outside connections (e.g. on Render)
HOST = os.environ.get("HOST") or "127.0.0.1"
PORT = int(os.environ.get("PORT") or 8000)
WEB_DIR = "web"
MAX_TARGET_LENGTH = 200
# Base64 adds about a third on top of the raw audio size
MAX_BODY_BYTES = security_utils.MAX_AUDIO_BYTES * 4 // 3 + 64 * 1024

# Ensure web directory exists
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(os.path.join(WEB_DIR, "data"), exist_ok=True)

class OmniSightHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/api/run':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
            except ValueError:
                self.send_error(400, "Invalid Content-Length.")
                return
            if content_length > MAX_BODY_BYTES:
                self.send_error(413, "Request body too large.")
                return
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                target = data.get('target')
                if not target or not isinstance(target, str) or len(target) > MAX_TARGET_LENGTH:
                    self.send_error(400, "Missing or invalid 'target' in request body.")
                    return
                
                audio_base64 = data.get('audio')
                filename = data.get('filename')
                audio_url = data.get('audio_url')
                temp_audio_path = None

                if audio_url:
                    try:
                        security_utils.validate_public_https_url(audio_url)
                    except security_utils.UnsafeURLError as e:
                        self.send_error(400, f"audio_url rejected: {e}")
                        return
                
                if audio_base64 and filename:
                    os.makedirs(security_utils.AUDIO_DIR, exist_ok=True)
                    if "," in audio_base64:
                        audio_base64 = audio_base64.split(",")[1]
                    
                    # Never trust the client's file name: build our own and keep it inside AUDIO_DIR
                    temp_audio_path = security_utils.confined_path(
                        security_utils.AUDIO_DIR, security_utils.safe_upload_name(filename))
                    try:
                        with open(temp_audio_path, "wb") as af:
                            af.write(base64.b64decode(audio_base64))
                        print(f"[+] Saved temporary audio file: {temp_audio_path}")
                    except Exception as e:
                        print(f"[-] Error saving audio file: {e}")
                
                # Delete the old battlecard file synchronously before returning response
                # so that the frontend's polling encounters a 404 until the new file is ready
                battlecard_path = os.path.join(WEB_DIR, "data", "latest_battlecard.json")
                if os.path.exists(battlecard_path):
                    try:
                        os.remove(battlecard_path)
                        print(f"[+] Cleared old battlecard at {battlecard_path}")
                    except Exception as e:
                        print(f"[-] Error removing old battlecard: {e}")
                
                # Delete old status file to reset frontend loader
                status_path = os.path.join(WEB_DIR, "data", "status.txt")
                with open(status_path, "w") as f:
                    f.write("[*] Initializing Agent Sandbox...\n")

                def run_agent():
                    print(f"[*] Server starting radar scan for: {target}")
                    cmd = [sys.executable, "agent_runtime.py"]
                    if temp_audio_path:
                        cmd.extend(["--audio", temp_audio_path])
                    if audio_url:
                        cmd.extend(["--audio-url", audio_url])
                    # "--" stops a target such as "--audio=/etc/passwd" from being read as an option
                    cmd.extend(["--", target])
                    
                    # Run and stream output
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    
                    with open(status_path, "a") as f:
                        for line in process.stdout:
                            print(line, end="") # keep logging to server console
                            f.write(line)
                            f.flush()
                    process.wait()

                threading.Thread(target=run_agent).start()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "running", "message": f"Radar deployed for {target}"}).encode())
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON.")
        else:
            self.send_error(404, "Endpoint not found.")

if __name__ == "__main__":
    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, OmniSightHandler)
    print(f"[+] OmniSight Local Server running at http://{HOST}:{PORT}")
    print("[+] Press Ctrl+C to stop.")
    httpd.serve_forever()
