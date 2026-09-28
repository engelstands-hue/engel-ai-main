"""Quick test: connects to Claude.ai and sends a test message. Run from Engel App dir."""
import sys
sys.path.insert(0, ".")
import engel_browser_ai_bridge as b

print(b.browser_ai_connect("claude"))
input("\nLog in if needed, then press Enter to send a test message...")
print("\nSending: 'hello, can you hear me?'")
result = b.browser_ai_send("hello, can you hear me?")
print("\n--- Response ---")
print(result)
print("--- End ---")
input("\nPress Enter to disconnect...")
print(b.browser_ai_disconnect())
