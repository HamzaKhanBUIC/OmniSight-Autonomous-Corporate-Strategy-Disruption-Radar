import json
import subprocess
import os
import threading
import base64
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", 8000))
WEB_DIR = "web"

# Ensure web directory exists
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(os.path.join(WEB_DIR, "data"), exist_ok=True)

class OmniSightHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/api/run':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                target = data.get('target')
                if not target:
                    self.send_error(400, "Missing 'target' in request body.")
                    return
                
                audio_base64 = data.get('audio')
                filename = data.get('filename')
                audio_url = data.get('audio_url')
                temp_audio_path = None
                
                if audio_base64 and filename:
                    os.makedirs(os.path.join(WEB_DIR, "temp_audio"), exist_ok=True)
                    if "," in audio_base64:
                        audio_base64 = audio_base64.split(",")[1]
                    
                    temp_audio_path = os.path.join(WEB_DIR, "temp_audio", f"{int(time.time())}_{filename}")
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
                    cmd = ["py", "agent_runtime.py", target]
                    if temp_audio_path:
                        cmd.extend(["--audio", temp_audio_path])
                    if audio_url:
                        cmd.extend(["--audio-url", audio_url])
                    
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
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, OmniSightHandler)
    print(f"[+] OmniSight Local Server running at http://localhost:{PORT}")
    print("[+] Press Ctrl+C to stop.")
    httpd.serve_forever()
