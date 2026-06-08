import pyttsx3
import threading

_lock = threading.Lock()


def speak(text):

    if not text:
        return

    print("VOICE FUNCTION CALLED")
    print(f"[VOICE] {text}")

    def _worker():

        try:

            engine = pyttsx3.init()

            # =====================================================
            # FEMALE VOICE
            # =====================================================

            voices = engine.getProperty("voices")

            for voice in voices:

                print(
                    f"VOICE FOUND: {voice.name}"
                )

                if "zira" in voice.name.lower():

                    engine.setProperty(
                        "voice",
                        voice.id
                    )

                    print(
                        f"USING VOICE: {voice.name}"
                    )

                    break

            # =====================================================
            # SPEED
            # =====================================================

            engine.setProperty(
                "rate",
                200
            )

            # =====================================================
            # SPEAK
            # =====================================================

            engine.say(
                str(text)
            )

            engine.runAndWait()

            engine.stop()

        except Exception as e:

            print(
                f"[VOICE ERROR] {e}"
            )

    threading.Thread(
        target=_worker,
        daemon=True
    ).start()