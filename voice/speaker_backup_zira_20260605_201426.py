import platform
import queue
import subprocess
import tempfile
import threading
import os

_speech_queue = queue.Queue()

def _speech_worker():

    while True:

        text = _speech_queue.get()

        try:

            if not text:
                continue

            print("VOICE FUNCTION CALLED")
            print(f"[VOICE] {text}")

            if platform.system().lower() != "windows":

                print("[VOICE] skipped: non-Windows host")
                continue

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                mode="w",
                encoding="utf-8"
            ) as f:

                f.write(str(text))
                temp_path = f.name

            ps_path = temp_path.replace("'", "''")

            command = (
                "$t = Get-Content -Raw -Encoding UTF8 '" + ps_path + "'; "
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Rate = 0; "
                "$s.Speak($t); "
                "$s.Dispose();"
            )

            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            try:
                os.remove(temp_path)
            except:
                pass

        except Exception as e:

            print(f"[VOICE ERROR] {e}")

        finally:

            _speech_queue.task_done()

_thread = threading.Thread(
    target=_speech_worker,
    daemon=True
)

_thread.start()

def speak(text):

    if not text:
        return

    _speech_queue.put(
        str(text)
    )
