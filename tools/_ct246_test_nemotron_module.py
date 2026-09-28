import engel_nemotron_lightning_runtime as m

print("file", m.__file__)
src = open(m.__file__, encoding="utf-8").read()
print("has_thinking_only_guard", "thinking-only content" in src)
print("has_no_thinking_instruction", "Never show a thinking process" in src)
out = m.generate("Say only: ENGEL_MAIN_OK", max_tokens=64, timeout=90)
print(
    {
        k: (str(out.get(k))[:300] if out.get(k) is not None else None)
        for k in ("ok", "text", "error", "via", "seconds")
    }
)
