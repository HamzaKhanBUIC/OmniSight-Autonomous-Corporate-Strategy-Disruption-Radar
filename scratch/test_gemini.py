import os
import openai
import httpx
from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("GEMINI_API_KEY")
print(f"Key exists: {bool(key)}")

# Disable SSL verification for development environments facing CA issues
client = openai.OpenAI(
    api_key=key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    http_client=httpx.Client(verify=False)
)

try:
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("Success:", response.choices[0].message.content)
except Exception as e:
    import traceback
    print("Error:")
    traceback.print_exc()
