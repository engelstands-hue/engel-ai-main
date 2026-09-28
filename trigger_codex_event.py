# Trigger a test Codex prompt to populate usage_state.json
import openai
import os

# --- Set your API key ---
openai.api_key = os.getenv("OPENAI_API_KEY")  # Or set your key directly

# --- Simple test prompt ---
prompt = "# Test function: return the square of a number\n"

try:
    response = openai.Completion.create(
        model="code-davinci-002",
        prompt=prompt,
        max_tokens=16,
        temperature=0
    )
    print("Codex test output:", response.choices[0].text.strip())
except Exception as e:
    print("Error triggering Codex:", e)