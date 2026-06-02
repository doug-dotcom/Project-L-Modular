import pyttsx3

engine = pyttsx3.init()

engine.setProperty("rate", 180)

def speak(text):

    try:

        if not text:
            return

        print(f"[VOICE] {text}")

        engine.say(str(text))

        engine.runAndWait()

    except Exception as e:

        print(f"[VOICE ERROR] {e}")
