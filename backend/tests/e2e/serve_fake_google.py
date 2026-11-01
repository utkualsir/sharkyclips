"""Run SharkyClips against the fake Google server for the browser test of "Connect with Google".

    python backend/tests/e2e/serve_fake_google.py [port]        (default 8131)

Starts the fake Google / YouTube server (backend/tests/fake_youtube.py) and SharkyClips on a
throwaway settings folder with a built-in Google client, then waits. Prints one JSON line:
{"app": "http://127.0.0.1:<port>", "google": "http://127.0.0.1:<port>", "home": "<folder>"}.
Then run: node backend/tests/e2e/youtube-connect.mjs  (see that file).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND / "tests"))

from fake_youtube import FakeYouTube  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8131
    home = Path(tempfile.mkdtemp(prefix="sharkyclips-e2e-"))
    (home / "workspace").mkdir()
    (home / "config.json").write_text(json.dumps({"workspace_dir": str(home / "workspace"), "llm_enabled": False,
                                                  "ui_language": "en"}), encoding="utf-8")
    shared = home / "google_client.json"
    shared.write_text(json.dumps({"client_id": "777-shared.apps.googleusercontent.com",
                                  "client_secret": "GOCSPX-public", "project_id": "sharkyclips",
                                  "verification": "unverified", "user_cap": 100}), encoding="utf-8")
    fake = FakeYouTube()
    fake.auth_page = True  # Allow / Cancel links, clicked by the browser test
    google = fake.start()
    env = {**os.environ, "SHARKYCLIPS_HOME": str(home), "SHARKYCLIPS_NO_MIGRATE": "1",
           "SHARKYCLIPS_YT_ENDPOINT": google, "SHARKYCLIPS_SHARED_CLIENT": str(shared),
           "SHARKYCLIPS_NO_BROWSER": "1", "SHARKYCLIPS_PUBLISH_LOOP": "0", "SHARKYCLIPS_NO_KEYCHAIN": "1"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen([sys.executable, str(BACKEND / "cli.py"), "serve", "--no-browser", "--port", str(port)],
                            env=env, cwd=str(BACKEND), creationflags=flags,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    app = f"http://127.0.0.1:{port}"
    for _ in range(300):
        try:
            urllib.request.urlopen(app + "/api/app", timeout=2)
            break
        except OSError:
            time.sleep(0.2)
    print(json.dumps({"app": app, "google": google, "home": str(home)}), flush=True)
    try:
        while proc.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        fake.stop()
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
