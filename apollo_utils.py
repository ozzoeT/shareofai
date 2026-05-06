import requests
import openai  # openai python sdk

# -----------------------------
# 1) Credenziali HARD-CODED (placeholder)
# -----------------------------
CLIENT_ID = "0c9aea8f-01bd-44a7-93b8-30760fca8b99"
CLIENT_SECRET = "de709386-4128-4c3b-a159-52e8e1f100a5"

# Token URL (per accesso via API Gateway esterno)
TOKEN_URL = "https://api-gw.boehringer-ingelheim.com/api/oauth/token"  # [1](https://boehringer.sharepoint.com/sites/z365apollocontrolcenter/SitePages/Guidebook-.aspx?web=1)

# Base URL Apollo (per accesso via API Gateway esterno)
APOLLO_BASE_URL = "https://api-gw.boehringer-ingelheim.com/apollo/llm-api"  # [1](https://boehringer.sharepoint.com/sites/z365apollocontrolcenter/SitePages/Guidebook-.aspx?web=1)

# Modello (esempio)
MODEL = "gpt-3.5-turbo"

def init_apollo_client():
    # OAuth2 Client Credentials -> Access Token
    token_data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    token_resp = requests.post(TOKEN_URL, data=token_data)
    token_resp.raise_for_status()
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise RuntimeError("No access_token returned from token endpoint")

    # init client OpenAI-style verso Apollo
    client = openai.OpenAI(
        api_key=access_token,
        base_url=APOLLO_BASE_URL
    )  
    return client


def send_message_to(client, system_prompt, user_prompt, model=MODEL, temperature=0.2, max_tokens=2000):
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp
#print(resp.choices[0].message.content)
