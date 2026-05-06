
# readme_apollo.md

## 1. Variabili d’ambiente richieste
Le variabili sono già salvate in questo ambiente
```bash
export APOLLO_CLIENT_ID="..."
export APOLLO_CLIENT_SECRET="..."
export APOLLO_TOKEN_URL="https://api-gw.boehringer-ingelheim.com/api/oauth/token"
```

## 3. Autenticazione OAuth2
```python
import os
import httpx
from httpx_auth import OAuth2ClientCredentials

TOKEN_URL = os.getenv("APOLLO_TOKEN_URL")
CLIENT_ID = os.getenv("APOLLO_CLIENT_ID")
CLIENT_SECRET = os.getenv("APOLLO_CLIENT_SECRET")

auth = OAuth2ClientCredentials(
    token_url=TOKEN_URL,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)
```

## 4. Chiamata stile OpenAI
```python
def apollo_chat(prompt: str):
    url = "https://api-gw.boehringer-ingelheim.com/apollo/llm-api/chat/completions"
    payload = {
        "model": "claude_4_5_sonnet",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    with httpx.Client(auth=auth, timeout=60) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
```

## 5. Chiamata stile Anthropic
```python
def apollo_messages(prompt: str):
    url = "https://api-gw.boehringer-ingelheim.com/apollo/llm-api/messages"
    payload = {
        "model": "claude_4_5_sonnet",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800
    }
    with httpx.Client(auth=auth, timeout=60) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["content"][0]["text"]
```

## 6. Controllo consumo
```python
def apollo_usage():
    url = "https://api-gw.boehringer-ingelheim.com/apollo/llm-api/customer/info"
    with httpx.Client(auth=auth, timeout=30) as client:
        return client.get(url).json()
```
