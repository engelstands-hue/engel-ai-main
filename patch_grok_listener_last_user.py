from pathlib import Path

p = Path("engel_rog_grok_cli_http_bridge.py")
s = p.read_text(encoding="utf-8")

start = s.index("def extract_prompt(data):")
end = s.index("\ndef run_grok(prompt: str) -> str:")

new_extract = r'''def _content_to_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                txt = item.get("text") or item.get("content")
                if isinstance(txt, str):
                    parts.append(txt)
        return "\n".join(parts).strip()
    return ""


def extract_prompt(data):
    if isinstance(data, dict):
        messages = data.get("messages")
        if isinstance(messages, list):
            # Use last user message only. Do not feed Grok the whole CT/system context.
            for m in reversed(messages):
                if isinstance(m, dict) and str(m.get("role", "")).lower() == "user":
                    text = _content_to_text(m.get("content"))
                    if text:
                        return text[-4000:]

            for m in reversed(messages):
                if isinstance(m, dict):
                    text = _content_to_text(m.get("content"))
                    if text:
                        return text[-4000:]

        for key in ["prompt", "message", "input", "text"]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[-4000:]

    return ""
'''

s = s[:start] + new_extract + s[end:]
s = s.replace('"--max-turns", "1",', '"--max-turns", "2",')
s = s.replace('"--disable-web-search",', '"--verbatim",\n            "--disable-web-search",')

p.write_text(s, encoding="utf-8")
print("patched Grok bridge: last user message only")
