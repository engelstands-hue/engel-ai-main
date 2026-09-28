import engel_nemotron_lightning_runtime as m

out = m.generate(
    "Review whether Engel AI Main can send and receive real messages. Be honest in 2 short sentences.",
    max_tokens=512,
    timeout=180,
)
print(
    {
        k: (str(out.get(k))[:500] if out.get(k) is not None else None)
        for k in ("ok", "text", "error", "via", "seconds")
    }
)
