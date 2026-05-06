"""
Quick connection diagnostic — run with: python debug_connection.py
Tests each step independently so we can pinpoint exactly where it fails.
"""
import os
import sys

print("=== Step 1: environment variables ===")
client_id = os.getenv("APOLLO_CLIENT_ID", "")
client_secret = os.getenv("APOLLO_CLIENT_SECRET", "")
print(f"  APOLLO_CLIENT_ID    : {'SET (' + client_id[:6] + '...)' if client_id else 'NOT SET'}")
print(f"  APOLLO_CLIENT_SECRET: {'SET (' + client_secret[:6] + '...)' if client_secret else 'NOT SET'}")

print("\n=== Step 2: import apollo_client ===")
try:
    from apollo_client import OpenAI, ApolloConfig
    print("  OK — apollo_client imported successfully")
except ImportError as e:
    print(f"  FAIL — {e}")
    print("  Try: pip install apollo-client  (or check the internal package name)")
    sys.exit(1)

print("\n=== Step 3: init ApolloConfig + OpenAI ===")
try:
    cfg = ApolloConfig(client_id=client_id, client_secret=client_secret)
    client = OpenAI(config=cfg)
    print("  OK — client created")
except Exception as e:
    print(f"  FAIL — {e}")
    sys.exit(1)

print("\n=== Step 4: list available models ===")
try:
    models = [m.id for m in client.models.list()]
    print(f"  OK — {len(models)} models found: {models[:5]}")
except Exception as e:
    print(f"  FAIL — {e}")

print("\n=== Step 5: single chat completion ===")
try:
    resp = client.chat.completions.create(
        model="claude_3_5_haiku",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with exactly one word: hello"},
        ],
        temperature=0.0,
        max_tokens=10,
    )
    print(f"  OK — response: {resp.choices[0].message.content!r}")
except Exception as e:
    print(f"  FAIL — {e}")
