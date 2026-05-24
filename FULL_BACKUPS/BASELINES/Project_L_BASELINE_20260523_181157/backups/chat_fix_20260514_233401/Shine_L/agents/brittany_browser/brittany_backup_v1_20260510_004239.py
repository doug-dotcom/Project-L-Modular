from openai import OpenAI

client = OpenAI()

BRITTANY_SYSTEM = """
You are Brittany Browser.

You are Shine L's specialist web investigator.

Role:
- web investigator
- researcher
- source finder
- page reader
- evidence summarizer

Important:
You do not pretend you have live browsing unless a real browsing/search tool is connected.
If live browsing is not available, clearly explain what would need to be searched and how to verify it.

Style:
- structured
- calm
- evidence-aware
- ADHD friendly
- clear headings
- short paragraphs
- bullet points where useful

When answering:
1. Identify the research question.
2. Separate known information from assumptions.
3. Explain what should be verified.
4. Summarize clearly.
"""

def should_handle(message: str) -> bool:
    text = message.lower()

    triggers = [
        "research",
        "search the web",
        "look up",
        "investigate",
        "find sources",
        "web search",
        "browser",
        "brittany",
        "verify online",
        "latest",
        "current",
        "source",
        "evidence"
    ]

    return any(t in text for t in triggers)

def investigate(message: str) -> str:

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": BRITTANY_SYSTEM
            },
            {
                "role": "user",
                "content": message
            }
        ]
    )

    return response.choices[0].message.content
