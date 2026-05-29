import os
import ssl
import asyncio
from dotenv import load_dotenv
load_dotenv()

# Globally bypass SSL verification for all python libraries (resolves local CA errors)
ssl._create_default_https_context = ssl._create_unverified_context

# Bypass litellm SSL verification via python attribute directly
import litellm
litellm.ssl_verify = False

# Bypass Cognee connection test
os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"

# Set all potential keys for Cognee
grok_key = os.environ.get("GROK_API_KEY")
gemini_key = os.environ.get("GEMINI_API_KEY")

if grok_key and grok_key != "your_grok_api_key_here":
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["LLM_MODEL"] = "openai/llama-3.3-70b-versatile"
    os.environ["LLM_API_KEY"] = grok_key
    os.environ["OPENAI_API_KEY"] = grok_key
    os.environ["OPENAI_API_BASE"] = "https://api.groq.com/openai/v1"
elif gemini_key:
    os.environ["LLM_PROVIDER"] = "gemini"
    os.environ["LLM_MODEL"] = "gemini/gemini-2.5-flash-lite"
    os.environ["LLM_API_KEY"] = gemini_key
    os.environ["OPENAI_API_KEY"] = gemini_key

if gemini_key:
    os.environ["EMBEDDING_PROVIDER"] = "gemini"
    os.environ["EMBEDDING_MODEL"] = "gemini/gemini-embedding-001"
    os.environ["EMBEDDING_API_KEY"] = gemini_key

import cognee

async def main():
    try:
        print("[+] Testing Cognee Memory addition...")
        await cognee.add("Competitor Test Company: robust strategy and GTM execution", "competitor_profiles")
        await cognee.cognify()
        print("[+] Cognee Graph Memory synced successfully!")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
