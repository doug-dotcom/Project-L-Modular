import os
import base64
from datetime import datetime
from openai import OpenAI

# =====================================================
# OPENAI CLIENT
# =====================================================

client = OpenAI()

# =====================================================
# PATHS
# =====================================================

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

IMAGE_DIR = os.path.join(
    ROOT_DIR,
    "generated_images"
)

os.makedirs(
    IMAGE_DIR,
    exist_ok=True
)

# =====================================================
# PIXIE ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "pixie",
        "picture",
        "image",
        "create image",
        "generate image",
        "make an image",
        "draw",
        "poster",
        "map poster",
        "visual",
        "diagram"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# CLEAN PROMPT
# =====================================================

def clean_prompt(message: str) -> str:

    prompt = message.strip()

    replacements = [

        "Pixie",
        "pixie",
        "create image",
        "generate image",
        "make an image"

    ]

    for r in replacements:

        prompt = prompt.replace(r, "")

    prompt = prompt.strip()

    if not prompt:

        prompt = (
            "Create a calm, clear, ADHD-friendly "
            "visual memory anchor poster in Shine style."
        )

    return prompt

# =====================================================
# CREATE IMAGE
# =====================================================

def create_image(message: str):

    try:

        prompt = clean_prompt(message)

        print("\n🎨 PIXIE PROMPT:", prompt)

        # =================================================
        # OPENAI IMAGE GENERATION
        # =================================================

        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )

        print("\n🎨 PIXIE RESPONSE:")
        print(response)

        # =================================================
        # SAFETY CHECK
        # =================================================

        if (
            not response
            or not response.data
            or len(response.data) == 0
        ):

            return {
                "reply":
                    "❌ Pixie received no image data.",
                "image_url": ""
            }

        # =================================================
    # DEBUG RESPONSE STRUCTURE
    # =================================================

    print("\n🎨 RAW IMAGE RESPONSE:")
    print(response)

    image_data = response.data[0]

    print("\n🎨 IMAGE DATA OBJECT:")
    print(image_data)

    image_url = getattr(
        image_data,
        "url",
        None
    )

    image_b64 = getattr(
        image_data,
        "b64_json",
        None
    )

    print("\n🎨 IMAGE URL:")
    print(image_url)

    print("\n🎨 HAS B64:")
    print(bool(image_b64))

    # =================================================
    # HANDLE URL RESPONSE
    # =================================================

    if image_url and not image_b64:

        return {

            "reply": (
                "# 🎨 Pixie Pictures\n\n"
                "Image created successfully.\n\n"
                "Using URL response mode."
            ),

            "image_url": image_url

        }

    # =================================================
    # SAFETY CHECK
    # =================================================

    if not image_b64:

        return {

            "reply":
                "❌ Pixie received no image payload.",

            "image_url": ""

        }

        if not image_b64:

            return {
                "reply":
                    "❌ Pixie image response was empty.",
                "image_url": ""
            }

        # =================================================
        # CREATE FILE NAME
        # =================================================

        filename = (
            "pixie_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".png"
        )

        path = os.path.join(
            IMAGE_DIR,
            filename
        )

        # =================================================
        # SAVE IMAGE
        # =================================================

        with open(path, "wb") as f:

            f.write(
                base64.b64decode(
                    image_b64
                )
            )

        print("\n🎨 PIXIE IMAGE SAVED:")
        print(path)

        # =================================================
        # SUCCESS RESPONSE
        # =================================================

        return {

            "reply": (
                "# 🎨 Pixie Pictures\n\n"
                "Image created successfully.\n\n"
                "Prompt used:\n"
                + prompt
            ),

            "image_url":
                "/generated_images/" + filename

        }

    except Exception as e:

        print("\n❌ PIXIE ERROR:")
        print(str(e))

        return {

            "reply":
                "❌ Pixie generation failed:\n\n"
                + str(e),

            "image_url": ""

        }

