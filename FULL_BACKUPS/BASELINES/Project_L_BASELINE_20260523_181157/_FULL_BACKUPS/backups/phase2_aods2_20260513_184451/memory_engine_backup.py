from dotenv import load_dotenv
load_dotenv()

import json
import os
from openai import OpenAI

from supabase import create_client

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


client = OpenAI()

# 🔥 LOCKED PATH (no more path issues)
BASE = r"memory"


FILES = {
    "structured": f"{BASE}/structured.json",
    "session": f"{BASE}/session.json"
}

def load(name):
    with open(FILES[name], "r") as f:
        return json.load(f)

def save(name, data):
    with open(FILES[name], "w") as f:
        json.dump(data, f, indent=2)


# -------------------------
# LOAD MEMORY
# -------------------------
def load(name):
    try:
        with open(FILES[name], "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

# -------------------------
# SAVE MEMORY
# -------------------------
def save(name, data):
    with open(FILES[name], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# -------------------------
# EXTRACT STRUCTURED MEMORY
# -------------------------
# -------------------------
# BUILD CONTEXT
# -------------------------
def build_context():
    try:
        res = (
    supabase.table("memories")
    .select("content")
    .eq("type", "fact")
    .order("created_at", desc=True)
    .limit(20)
    .execute()
)

        structured = [x["content"] for x in res.data]
    except Exception as e:
        print("❌ Supabase read failed, using JSON fallback:", e)
        structured = load("structured")[-20:]
    session = load("session")[-10:]

    context = "Known facts:\n"

    for item in structured:
        context += f"- {item}\n"

    context += "\nRecent:\n"

    for item in session:
        context += f"- {item}\n"

    return context

# -------------------------
# PROCESS MESSAGE
# -------------------------
def process(msg):
    session = load("session")

    session.append(msg)
    save("session", session)

    extract_structured(msg)

# -------------------------
# EXTRACT STRUCTURED MEMORY (FIXED)
# -------------------------
def extract_structured(msg):
    import re

    prompt = f"""
Extract important long-term facts about the user.

Return STRICT JSON:

{{"facts": ["fact1","fact2"]}}

Message:
{msg}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        raw = res.choices[0].message.content.strip()
        print("🧠 RAW AI RESPONSE:", raw)

        json_match = re.search(r"\{.*\}", raw, re.DOTALL)

        if not json_match:
            print("❌ No JSON found")
            return

        obj = json.loads(json_match.group())

        if "facts" not in obj:
            return

        structured = load("structured")

        for f in obj["facts"]:
            if isinstance(f, str) and f not in structured:
                structured.append(f)
        save_structured_to_supabase(f)

        save("structured", structured)

    except Exception as e:
        print("❌ Memory extraction failed:", e)



# -------------------------
# SAVE STRUCTURED TO SUPABASE
# -------------------------
def save_structured_to_supabase(fact):
    try:
        (
    supabase.table("memories")
    .select("content")
    .eq("type", "fact")
    .order("created_at", desc=True)
    .limit(20)
    .execute()
)
        print("🟢 Saved FACT to Supabase:", fact)
    except Exception as e:
        print("❌ Supabase structured save error:", e)


# =========================
# ELLIE PHASE 2 OVERRIDES
# DEDUPE + CATEGORIES + SMART CONTEXT
# =========================

def _norm_text(text):
    import re
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text

def _infer_category(text):
    t = _norm_text(text)

    categories = {
        "identity": ["name", "called", "born", "birthday", "doug", "douglas", "profile"],
        "family": ["kids", "children", "son", "daughter", "iyla", "ashton", "luella", "mehlia", "family"],
        "health": ["diagnosed", "adhd", "ocpd", "depression", "anxiety", "asthma", "mental", "health", "medical"],
        "sport": ["hockey", "sport", "team", "play", "brisbane", "queensland"],
        "recovery": ["na", "aa", "clean", "recovery", "alcohol", "addiction", "narcotics anonymous"],
        "work": ["work", "army", "career", "job", "assistant", "ai"],
        "preference": ["favourite", "favorite", "prefers", "likes", "values", "wants"],
        "travel": ["flight", "airport", "travel", "cairns", "brisbane"],
        "relationship": ["leah", "lyndal", "relationship", "partner"],
    }

    for category, words in categories.items():
        if any(w in t for w in words):
            return category

    return "general"

def _importance_score(text):
    t = _norm_text(text)
    score = 0.5

    high_words = ["children", "kids", "diagnosed", "born", "clean date", "truth protocol", "name", "family"]
    medium_words = ["favourite", "favorite", "hockey", "values", "prefers", "flight"]

    if any(w in t for w in high_words):
        score = 0.9
    elif any(w in t for w in medium_words):
        score = 0.7

    return score

def _is_duplicate_fact(fact, existing):
    nf = _norm_text(fact)

    for item in existing:
        ni = _norm_text(item)

        if nf == ni:
            return True

        if len(nf) > 12 and len(ni) > 12:
            if nf in ni or ni in nf:
                return True

    return False

def _load_supabase_facts(limit=1000):
    try:
        res = (
            supabase.table("memories")
            .select("content")
            .eq("type", "fact")
            .limit(limit)
            .execute()
        )

        if not res.data:
            return []

        return [x.get("content", "") for x in res.data if x.get("content")]

    except Exception as e:
        print("Supabase fact load failed:", e)
        return []

def save_structured_to_supabase(fact):
    try:
        existing = _load_supabase_facts()

        if _is_duplicate_fact(fact, existing):
            print("Skipped duplicate FACT:", fact)
            return

        category = _infer_category(fact)
        importance = _importance_score(fact)

        supabase.table("memories").insert({
            "type": _infer_type(fact),
            "category": category,
            "content": fact,
            "importance": importance,
            "metadata": {
                "source": "ellie_phase2",
                "category": category
            }
        }).execute()

        print("Saved FACT to Supabase:", fact)

    except Exception as e:
        print("Supabase structured save error:", e)

def extract_structured(msg):
    import re

    prompt = f"""
Extract important long-term facts about the user.

Rules:
- Return STRICT JSON only.
- Only include stable facts, preferences, identity details, family details, health/recovery facts, goals, or important life context.
- Do not include random temporary chat unless the user asks to save it.
- Avoid duplicate wording if the same fact already exists.

Return format:
{{"facts": ["fact1", "fact2"]}}

Message:
{msg}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        raw = res.choices[0].message.content.strip()
        print("RAW MEMORY EXTRACTION:", raw)

        json_match = re.search(r"\{.*\}", raw, re.DOTALL)

        if not json_match:
            print("No JSON found in memory extraction")
            return

        obj = json.loads(json_match.group())

        if "facts" not in obj:
            return

        structured = load("structured")

        for f in obj["facts"]:
            if isinstance(f, str):
                f = f.strip()
                if f and not _is_duplicate_fact(f, structured):
                    structured.append(f)
                    save_structured_to_supabase(f)

        save("structured", structured)

    except Exception as e:
        print("Memory extraction failed:", e)

def build_context():
    try:
        session = load("session")[-10:]
    except Exception:
        session = []

    latest = session[-1] if session else ""
    latest_terms = set(_norm_text(latest).split())

    try:
        res = (
            supabase.table("memories")
            .select("content, category, importance, created_at")
            .eq("type", "fact")
            .order("created_at", desc=True)
            .limit(120)
            .execute()
        )

        rows = res.data or []

        scored = []
        seen = set()

        for row in rows:
            content = row.get("content", "")
            key = _norm_text(content)

            if not content or key in seen:
                continue

            seen.add(key)

            words = set(key.split())
            overlap = len(words & latest_terms)
            importance = row.get("importance") or 0.5

            score = overlap + float(importance)

            scored.append((score, content))

        scored.sort(reverse=True, key=lambda x: x[0])

        structured = [x[1] for x in scored[:35]]

        if not structured:
            structured = load("structured")[-35:]

    except Exception as e:
        print("Supabase read failed, using JSON fallback:", e)
        structured = load("structured")[-35:]

    context = "Known facts:\n"

    for item in structured:
        context += f"- {item}\n"

    context += "\nRecent:\n"

    for item in session:
        context += f"- {item}\n"

    return context

def migrate_existing_structured_to_supabase():
    try:
        structured = load("structured")
        count = 0

        for fact in structured:
            if isinstance(fact, str) and fact.strip():
                before = len(_load_supabase_facts())
                save_structured_to_supabase(fact.strip())
                after = len(_load_supabase_facts())
                if after > before:
                    count += 1

        print("Migration complete. Added facts:", count)
        return count

    except Exception as e:
        print("Migration failed:", e)
        return 0

# END ELLIE PHASE 2 OVERRIDES



def _infer_type(text):
    t = text.lower()

    if any(w in t for w in ["favourite", "favorite", "likes", "prefers", "values"]):
        return "preference"

    if any(w in t for w in ["today", "yesterday", "flight", "meeting", "going"]):
        return "event"

    if any(w in t for w in ["always", "often", "regularly", "usually"]):
        return "pattern"

    if any(w in t for w in ["i am", "i'm", "identity", "person"]):
        return "identity"

    return "fact"


# =========================
# ELLIE PHASE 3 SEMANTIC RECALL
# Embeddings + meaning-based memory
# =========================

def _embed_text(text):
    try:
        if not text or not str(text).strip():
            return None

        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=str(text)
        )

        return res.data[0].embedding

    except Exception as e:
        print("Embedding failed:", e)
        return None


def _cosine_similarity(a, b):
    try:
        if not a or not b:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(y * y for y in b) ** 0.5

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    except Exception:
        return 0.0


def save_structured_to_supabase(fact):
    try:
        existing = _load_supabase_facts()

        if _is_duplicate_fact(fact, existing):
            print("Skipped duplicate FACT:", fact)
            return

        category = _infer_category(fact)
        importance = _importance_score(fact)
        memory_type = _infer_type(fact)
        embedding = _embed_text(fact)

        metadata = {
            "source": "ellie_phase3_semantic",
            "category": category,
            "semantic": True
        }

        if embedding:
            metadata["embedding"] = embedding

        supabase.table("memories").insert({
            "type": memory_type,
            "category": category,
            "content": fact,
            "importance": importance,
            "metadata": metadata
        }).execute()

        print("Saved semantic memory to Supabase:", fact)

    except Exception as e:
        print("Supabase semantic save error:", e)


def build_context():
    try:
        session = load("session")[-10:]
    except Exception:
        session = []

    latest = session[-1] if session else ""
    latest_terms = set(_norm_text(latest).split())
    query_embedding = _embed_text(latest)

    try:
        res = (
            supabase.table("memories")
            .select("id, content, category, type, importance, metadata, created_at")
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )

        rows = res.data or []

        scored = []
        seen = set()

        for row in rows:
            content = row.get("content", "")
            key = _norm_text(content)

            if not content or key in seen:
                continue

            seen.add(key)

            words = set(key.split())
            keyword_overlap = len(words & latest_terms)

            importance = row.get("importance") or 0.5
            metadata = row.get("metadata") or {}
            memory_embedding = metadata.get("embedding")

            semantic_score = 0.0
            if query_embedding and memory_embedding:
                semantic_score = _cosine_similarity(query_embedding, memory_embedding)

            # balanced scoring: meaning + keyword + importance
            score = (semantic_score * 4.0) + keyword_overlap + float(importance)

            scored.append((score, content))

        scored.sort(reverse=True, key=lambda x: x[0])

        structured = [x[1] for x in scored[:35]]

        if not structured:
            structured = load("structured")[-35:]

    except Exception as e:
        print("Semantic Supabase read failed, using JSON fallback:", e)
        structured = load("structured")[-35:]

    context = "Known facts:\n"

    for item in structured:
        context += f"- {item}\n"

    context += "\nRecent:\n"

    for item in session:
        context += f"- {item}\n"

    return context


def backfill_embeddings_to_supabase(limit=500):
    try:
        res = (
            supabase.table("memories")
            .select("id, content, metadata")
            .limit(limit)
            .execute()
        )

        rows = res.data or []
        updated = 0

        for row in rows:
            metadata = row.get("metadata") or {}

            if metadata.get("embedding"):
                continue

            content = row.get("content")
            if not content:
                continue

            embedding = _embed_text(content)
            if not embedding:
                continue

            metadata["embedding"] = embedding
            metadata["semantic"] = True
            metadata["source"] = metadata.get("source", "ellie_phase3_backfill")

            supabase.table("memories").update({
                "metadata": metadata
            }).eq("id", row["id"]).execute()

            updated += 1

        print("Semantic backfill complete. Updated:", updated)
        return updated

    except Exception as e:
        print("Semantic backfill failed:", e)
        return 0

# END ELLIE PHASE 3 SEMANTIC RECALL



# =========================
# PROACTIVE INTELLIGENCE
# =========================
def generate_proactive_insight(latest_msg):
    try:
        facts = _load_supabase_facts(200)
        msg = latest_msg.lower()

        if "kids" in msg:
            return "You often bring things back to your kids — they seem to be a strong anchor point for you."

        if "hockey" in msg:
            return "You consistently mention hockey — it looks like an important structure in your week."

        if "honesty" in msg or "truth" in msg:
            return "You value honesty deeply — that Truth Protocol you follow is a big part of how you operate."

        if "how many" in msg or "what is" in msg:
            return "You tend to check facts you already know — that’s a good way to reinforce clarity."

        if len(facts) > 50:
            return "You’ve built a strong memory base — patterns are starting to form in how you think and act."

        return None

    except Exception as e:
        print("Proactive failed:", e)
        return None




# =========================
# EMOTIONAL INTELLIGENCE
# =========================

def detect_emotional_state(text):
    try:
        t = str(text).lower()

        if any(w in t for w in ["stressed", "overwhelmed", "anxious", "panic", "pressure"]):
            return "activated"

        if any(w in t for w in ["tired", "exhausted", "flat", "low", "burnt"]):
            return "low_energy"

        if any(w in t for w in ["good", "great", "happy", "calm", "clear"]):
            return "regulated"

        if any(w in t for w in ["confused", "lost", "not sure", "unclear"]):
            return "uncertain"

        return "neutral"

    except Exception as e:
        print("Emotion detection failed:", e)
        return "neutral"


def generate_emotional_tone(state):
    try:
        if state == "activated":
            return "Keep responses calm, grounding, and simple. Reduce complexity."

        if state == "low_energy":
            return "Keep responses short, supportive, and low effort to read."

        if state == "uncertain":
            return "Use gentle guidance and clarity. Avoid overwhelming detail."

        if state == "regulated":
            return "Normal tone. Can expand slightly if useful."

        return "Normal tone."

    except Exception as e:
        print("Tone generation failed:", e)
        return "Normal tone."






# =====================================================
# LIVE MEMORY AUDIT V1
# =====================================================

def get_memory_record_count():

    try:

        memories = _load_supabase_facts()

        if not memories:
            return 0

        return len(memories)

    except Exception as e:

        print("MEMORY COUNT ERROR:", e)

        return 0

def build_full_memory_audit():

    try:

        memories = _load_supabase_facts()

        if not memories:

            return (
                "Memory Audit\n\n"
                "No memories currently loaded."
            )

        total = len(memories)

        categories = {}

        types = {}

        for item in memories:

            category = item.get(
                "category",
                "unknown"
            )

            mem_type = item.get(
                "type",
                "unknown"
            )

            categories[category] = (
                categories.get(category, 0) + 1
            )

            types[mem_type] = (
                types.get(mem_type, 0) + 1
            )

        reply = "Memory Audit\n\n"

        reply += (
            "Total Supabase memories: "
            + str(total)
            + "\n\n"
        )

        reply += "By category:\n"

        for key, value in sorted(
            categories.items()
        ):

            reply += (
                "- "
                + str(key)
                + ": "
                + str(value)
                + "\n"
            )

        reply += "\nBy type:\n"

        for key, value in sorted(
            types.items()
        ):

            reply += (
                "- "
                + str(key)
                + ": "
                + str(value)
                + "\n"
            )

        return reply.strip()

    except Exception as e:

        print("FULL MEMORY AUDIT ERROR:", e)

        return (
            "Memory Audit\n\n"
            "Audit failed to load."
        )




# =====================================================
# RELATIONAL MEMORY FOUNDATIONS V1
# =====================================================

RELATIONAL_MEMORY_FIELDS = [

    "who",
    "what",
    "where",
    "when",
    "outcome",
    "emotion"

]

TOPIC_CLUSTERS = {

    "fishing": [
        "fish",
        "pier",
        "bait",
        "boat",
        "fishing"
    ],

    "hockey": [
        "hockey",
        "goal",
        "field",
        "game",
        "training"
    ],

    "family": [
        "kids",
        "daughter",
        "son",
        "luella",
        "ashton",
        "family"
    ]

}

def detect_topic_cluster(text):

    lower = text.lower()

    best_cluster = None
    best_score = 0

    for cluster, keywords in TOPIC_CLUSTERS.items():

        score = 0

        for keyword in keywords:

            if keyword in lower:
                score += 1

        if score > best_score:

            best_score = score
            best_cluster = cluster

    return best_cluster

def build_relational_memory_context(memories):

    if not memories:

        return ""

    context = []

    for memory in memories[:5]:

        parts = []

        who = memory.get("who")
        what = memory.get("what")
        where = memory.get("where")
        when = memory.get("when")
        outcome = memory.get("outcome")
        emotion = memory.get("emotion")

        if who:
            parts.append("who: " + str(who))

        if what:
            parts.append("what: " + str(what))

        if where:
            parts.append("where: " + str(where))

        if when:
            parts.append("when: " + str(when))

        if outcome:
            parts.append("outcome: " + str(outcome))

        if emotion:
            parts.append("emotion: " + str(emotion))

        if parts:

            context.append(
                " | ".join(parts)
            )

    if not context:

        return ""

    return (
        "\n\nRELATIONAL MEMORY CONTEXT:\n"
        + "\n".join(context)
    )

def extract_relational_memory(user_msg):

    topic = detect_topic_cluster(
        user_msg
    )

    if not topic:

        return []

    memories = _load_supabase_facts()

    if not memories:

        return []

    related = []

    for memory in memories:

        memory_text = json.dumps(
            memory
        ).lower()

        if topic in memory_text:

            related.append(memory)

    return related[:5]

