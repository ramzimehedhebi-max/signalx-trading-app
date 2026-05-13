"""
Translate the latest en.json keys into ar/es/de/it/pt/zh JSON files.
We treat en.json as canonical (source of truth) and FILL IN missing leaf keys
in each target locale, preserving existing translations. Translation is done in
one Claude call per target language with strict JSON-out instructions.
"""
import os, json, asyncio
from pathlib import Path
from emergentintegrations.llm.chat import LlmChat, UserMessage

LOCALES_DIR = Path("/app/frontend/src/i18n/locales")
SRC = "en"
TARGETS = ["ar", "es", "de", "it", "pt", "zh"]
KEY = os.environ["EMERGENT_LLM_KEY"]

LANG_NAME = {
    "ar": "Arabic (العربية)",
    "es": "Spanish (Español)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Brazilian Portuguese (Português brasileiro)",
    "zh": "Simplified Chinese (简体中文)",
}


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, prefix + ("." if prefix else "") + k))
    else:
        out[prefix] = obj
    return out


def unflatten(flat):
    out = {}
    for path, v in flat.items():
        parts = path.split(".")
        cur = out
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out


async def translate_for(lang: str, missing: dict[str, str]) -> dict[str, str]:
    if not missing:
        return {}
    sys_msg = (
        f"You are a professional translator. Translate provided UI strings from English to "
        f"{LANG_NAME[lang]}. Keep ALL placeholder tokens like {{{{name}}}}, {{{{date}}}}, "
        f"{{{{cap}}}}, {{{{pct}}}}, {{{{days}}}}, {{{{n}}}}, {{{{count}}}}, {{{{interval}}}}, "
        f"{{{{sl}}}}, {{{{tp}}}}, {{{{pos}}}}, {{{{type}}}}, {{{{trade}}}}, {{{{min}}}}, "
        f"{{{{email}}}}, {{{{v}}}}, {{{{sym}}}} EXACTLY. Keep emojis. Keep <buy/> tag exact. "
        f"Output ONLY a JSON object mapping key -> translated string. NO markdown, NO commentary."
    )
    user_prompt = "Translate these UI strings to " + LANG_NAME[lang] + ":\n\n" + json.dumps(missing, ensure_ascii=False, indent=2)
    chat = LlmChat(api_key=KEY, session_id=f"i18n-{lang}", system_message=sys_msg).with_model("anthropic", "claude-sonnet-4-5-20250929")
    resp = await chat.send_message(UserMessage(text=user_prompt))
    txt = resp.strip()
    # strip possible markdown fences
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1]
        if txt.endswith("```"):
            txt = txt.rsplit("```", 1)[0]
        if txt.startswith("json"):
            txt = txt[4:].lstrip()
    try:
        return json.loads(txt)
    except Exception as e:
        print(f"JSON parse failed for {lang}: {e}\nFirst 500 chars:\n{txt[:500]}")
        return {}


async def main():
    src = json.load(open(LOCALES_DIR / f"{SRC}.json"))
    src_flat = flatten(src)
    print(f"EN has {len(src_flat)} keys")

    for lang in TARGETS:
        path = LOCALES_DIR / f"{lang}.json"
        existing = json.load(open(path)) if path.exists() else {}
        ex_flat = flatten(existing)
        # Missing = present in EN, absent in lang
        missing = {k: v for k, v in src_flat.items() if k not in ex_flat}
        print(f"{lang}: {len(missing)} missing keys")
        if not missing:
            continue
        # Batch translate
        translated = await translate_for(lang, missing)
        # Merge with existing
        merged_flat = {**ex_flat, **translated}
        # Add fallback for any STILL missing keys (use EN as fallback)
        for k, v in src_flat.items():
            if k not in merged_flat:
                merged_flat[k] = v
        unflat = unflatten(merged_flat)
        with open(path, "w") as f:
            json.dump(unflat, f, ensure_ascii=False, indent=2)
        print(f"{lang}: wrote {len(merged_flat)} total keys")


if __name__ == "__main__":
    asyncio.run(main())
