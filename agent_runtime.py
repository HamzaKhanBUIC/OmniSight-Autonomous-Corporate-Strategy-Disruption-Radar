import os
import sys
import re
import json
import asyncio
import httpx
import ssl
from dotenv import load_dotenv

# Globally bypass SSL verification for all python libraries (resolves local CA errors)
ssl._create_default_https_context = ssl._create_unverified_context

# Load environment variables from .env file
load_dotenv()

# Configure Cognee to use Groq (if available) or Gemini Direct natively via LiteLLM
grok_key = os.environ.get("GROK_API_KEY")
gemini_key = os.environ.get("GEMINI_API_KEY")

if grok_key and grok_key != "your_grok_api_key_here":
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["LLM_MODEL"] = "openai/llama-3.1-8b-instant"
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

os.environ["LITELLM_SSL_VERIFY"] = "False"
os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"

try:
    import litellm
    litellm.ssl_verify = False
except ImportError:
    pass

# Attempt to load openai and cognee
try:
    import openai
except ImportError:
    print("[-] ERROR: 'openai' package is required. Run: pip install openai")
    sys.exit(1)

try:
    import cognee
    COGNEE_AVAILABLE = True
except ImportError:
    COGNEE_AVAILABLE = False
    print("[!] NOTICE: 'cognee' not found. Agent memory will be disabled. Run: pip install cognee")

def initialize_omnisight():
    # Ensure mandatory API tokens are active
    bd_key = os.environ.get("BRIGHT_DATA_API_KEY")
    is_simulation = False
    if not bd_key or bd_key == "your_actual_bright_data_api_key_here":
        print("[!] NOTICE: Bright Data API Key missing or placeholder. Enabling Simulation Mode.")
        is_simulation = True

    # Initialize Groq Client (Primary Engine)
    grok_key = os.environ.get("GROK_API_KEY")
    grok_client = None
    if grok_key and grok_key != "your_grok_api_key_here":
        print("[+] Initializing Groq Primary Client...")
        grok_client = openai.OpenAI(
            api_key=grok_key,
            base_url="https://api.groq.com/openai/v1",
            http_client=httpx.Client(verify=False)
        )
    else:
        print("[-] WARNING: GROK_API_KEY missing or placeholder.")

    # Initialize Gemini Direct Client (Fallback/Backup)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_client = None
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        print("[+] Initializing Gemini Direct Backup Client...")
        gemini_client = openai.OpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            http_client=httpx.Client(verify=False)
        )
    else:
        print("[-] WARNING: GEMINI_API_KEY missing or placeholder.")

    # Load our engineered system instructions
    try:
        with open("system_instructions.txt", "r") as f:
            instructions = f.read()
    except FileNotFoundError:
        print("[-] ERROR: system_instructions.txt not found. Create it first.")
        sys.exit(1)

    if is_simulation:
        print("[+] Provisioning OmniSight Agent Sandbox (Simulation Mode)...")
        instructions += "\n\nSIMULATION MODE ACTIVE: Do not attempt to write python scripts or hit Bright Data APIs. Instead, use your internal knowledge base to hallucinate highly realistic, deep-dive strategic indicators, job hiring trends, and feature parity datasets for the target company. Just generate the final unstructured analysis and then output the final JSON battlecard."
    else:
        print("[+] Provisioning OmniSight Agent Sandbox with Web Unlocker...")

    return grok_client, gemini_client, is_simulation, instructions

# Cognee Memory Functions
async def setup_cognee_memory(target_company, summary_text):
    if not COGNEE_AVAILABLE: return
    try:
        print(f"[+] Syncing {target_company} profile into Cognee Graph Memory...")
        await cognee.add(f"Competitor {target_company}: {summary_text}", "competitor_profiles")
        await cognee.cognify()
    except Exception as e:
        print(f"[-] Cognee Memory Sync Failed: {e}")

async def query_cognee_memory(target_company):
    if not COGNEE_AVAILABLE: return "No memory available."
    try:
        print(f"[+] Querying Cognee Memory for historical comparisons to {target_company}...")
        results = await cognee.search(query_text=f"Historical vulnerabilities and pricing strategies of competitors", query_type="insight")
        return str(results)
    except Exception:
        return "Memory query failed."

async def fetch_bright_data_serp(query: str, api_key: str):
    """
    Fetches Google search results using Bright Data SERP API.
    Returns a tuple (clean_text, top_url).
    """
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.google.com/search?q={encoded_query}&num=10"
    
    url = "https://api.brightdata.com/request"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "zone": os.environ.get("BRIGHT_DATA_SERP_ZONE", "serp_api1"),
        "url": search_url,
        "format": "raw"
    }
    try:
        print(f"[+] Bright Data: Fetching SERP data for query '{query}'...")
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            if response.status_code == 200:
                html = response.text
                
                # Extract first external link from raw Google Search HTML before stripping tags
                urls = re.findall(r'href="([^"]+)"', html)
                top_url = None
                for url_candidate in urls:
                    if "url?q=" in url_candidate:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url_candidate).query)
                        target = parsed.get("q")
                        if target:
                            candidate = target[0]
                            if "google.com" not in candidate and candidate.startswith("http"):
                                top_url = candidate
                                break
                    elif url_candidate.startswith("http") and "google.com" not in url_candidate:
                        top_url = url_candidate
                        break

                # Remove scripts, styles and other tags to clean the content
                clean_text = re.sub(r'<script[^>]*?>.*?</script>', '', html, flags=re.DOTALL)
                clean_text = re.sub(r'<style[^>]*?>.*?</style>', '', clean_text, flags=re.DOTALL)
                clean_text = re.sub(r'<[^<]+?>', ' ', clean_text)
                # Clean extra whitespace
                clean_lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
                clean_text = "\n".join(clean_lines)[:3000] # Limit to protect context window
                return clean_text, top_url
            else:
                print(f"[-] Bright Data SERP failed with status {response.status_code}: {response.text}")
                return f"Failed to fetch search results from Bright Data SERP. Status: {response.status_code}", None
    except Exception as e:
        print(f"[-] Bright Data SERP exception: {e}")
        return f"Failed to fetch search results due to exception: {e}", None

async def fetch_bright_data_unlocker(target_url: str, api_key: str) -> str:
    """
    Fetches raw site content using Bright Data Web Unlocker.
    """
    url = "https://api.brightdata.com/request"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "zone": os.environ.get("BRIGHT_DATA_UNLOCKER_ZONE", "web_unlocker1"),
        "url": target_url,
        "format": "raw"
    }
    try:
        print(f"[+] Bright Data: Scraping site via Web Unlocker: {target_url}...")
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(url, json=payload, headers=headers, timeout=25.0)
            if response.status_code == 200:
                html_content = response.text
                text = re.sub('<[^<]+?>', '', html_content)
                text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])[:1500]
                return text if text else "No content extracted."
            else:
                print(f"[-] Bright Data Web Unlocker failed with status {response.status_code}: {response.text}")
                return f"Failed to unlock {target_url}. Status: {response.status_code}"
    except Exception as e:
        print(f"[-] Bright Data Web Unlocker exception: {e}")
        return f"Failed to unlock due to exception: {e}"

async def transcribe_audio_speechmatics(audio_path: str, api_key: str) -> str:
    from speechmatics.batch import AsyncClient, TranscriptionConfig
    try:
        print(f"[+] Speechmatics: Transcribing audio file {audio_path}...")
        os.environ["SPEECHMATICS_API_KEY"] = api_key
        async with AsyncClient() as client:
            config = TranscriptionConfig(diarization="speaker")
            result = await client.transcribe(
                audio_file=audio_path, 
                transcription_config=config
            )
            return result.transcript_text
    except Exception as e:
        print(f"[-] Speechmatics transcription exception: {e}")
        return f"Audio transcription failed: {e}"

def run_analysis(target_company: str, audio_path: str = None, audio_url: str = None):
    grok_client, gemini_client, is_simulation, instructions = initialize_omnisight()
    bd_key = os.environ.get("BRIGHT_DATA_API_KEY")
    
    # Retrieve memory
    historical_memory = asyncio.run(query_cognee_memory(target_company))

    if is_simulation:
        session_prompt = f"""
        TARGET COMPANY: {target_company}
        
        COGNEE GRAPH MEMORY CONTEXT:
        {historical_memory}
        
        SIMULATION MODE ACTIVE.
        Generate a highly realistic deep-dive disruption analysis for {target_company}.
        Output the final Market Disruption Battlecard including the required JSON schema at the end.
        """
        import time
        print(f"[#] Deploying Disruption Radar against target: '{target_company}'...")
        time.sleep(0.5)
        print("[LOG] Initiating simulated SERP discovery phase...")
        time.sleep(0.5)
        print("[LOG] Synthesizing simulated intelligence profile...")
    else:
        # Live queries execution
        hiring_query = f"{target_company} technical hiring job postings career"
        pricing_query = f"{target_company} pricing changes subscription plans"
        sentiment_query = f"{target_company} outage bug issues review forums"
        
        async def run_bright_data_queries():
            # Fire all 3 SERP queries concurrently
            results = await asyncio.gather(
                fetch_bright_data_serp(hiring_query, bd_key),
                fetch_bright_data_serp(pricing_query, bd_key),
                fetch_bright_data_serp(sentiment_query, bd_key)
            )
            h_data, t_url = results[0]
            p_data, _ = results[1]
            s_data, _ = results[2]
            
            # Pulling a deep page scrape using Web Unlocker for top result in hiring
            ds_data = "No URL found for deep scraping."
            if t_url:
                ds_data = await fetch_bright_data_unlocker(t_url, bd_key)
                
            return h_data, p_data, s_data, ds_data
            
        hiring_data, pricing_data, sentiment_data, deep_scrape_data = asyncio.run(run_bright_data_queries())

        session_prompt = f"""
        TARGET COMPANY: {target_company}
        
        COGNEE GRAPH MEMORY CONTEXT:
        {historical_memory}

        LIVE DATA RETURNED VIA BRIGHT DATA SERP & WEB UNLOCKER:
        
        1. Hiring Signals (SERP):
        {hiring_data}
        
        2. Pricing Signals (SERP):
        {pricing_data}
        
        3. Sentiment Signals (SERP):
        {sentiment_data}
        
        4. Deep Scraping Insight (Web Unlocker):
        {deep_scrape_data}
        """
        
        if audio_url:
            import time
            try:
                print(f"[+] Processing audio URL: {audio_url}")
                os.makedirs(os.path.join("web", "temp_audio"), exist_ok=True)
                download_path = os.path.join("web", "temp_audio", f"{int(time.time())}_url_audio.media")
                
                if "youtube.com" in audio_url or "youtu.be" in audio_url:
                    print("[+] YouTube URL detected. Extracting audio stream using yt-dlp...")
                    try:
                        import yt_dlp
                        ydl_opts_simple = {
                            'format': 'bestaudio/best',
                            'outtmpl': os.path.join("web", "temp_audio", f"{int(time.time())}_yt_audio.%(ext)s"),
                            'nocheckcertificate': True,
                        }
                        with yt_dlp.YoutubeDL(ydl_opts_simple) as ydl:
                            info = ydl.extract_info(audio_url, download=True)
                            audio_path = ydl.prepare_filename(info)
                            print(f"[+] Successfully extracted YouTube audio to {audio_path}")
                    except Exception as yt_err:
                        print(f"[-] yt-dlp extraction failed: {yt_err}")
                
                if not audio_path:
                    print(f"[+] Downloading raw audio from direct link: {audio_url}...")
                    with httpx.Client(verify=False, follow_redirects=True) as hclient:
                        with open(download_path, "wb") as f:
                            with hclient.stream("GET", audio_url) as r:
                                for chunk in r.iter_bytes():
                                    f.write(chunk)
                    audio_path = download_path
                    print(f"[+] Saved raw media stream to {audio_path}")
            except Exception as e:
                print(f"[-] Audio URL download or extraction failed: {e}")

        if audio_path:
            sm_key = os.environ.get("SPEECHMATICS_API_KEY")
            if sm_key and sm_key != "your_speechmatics_api_key_here":
                transcript = asyncio.run(transcribe_audio_speechmatics(audio_path, sm_key))
                session_prompt += f"\n5. Audio Intelligence (Speechmatics Transcript):\n{transcript}\n"
            else:
                print("[-] WARNING: SPEECHMATICS_API_KEY missing or placeholder. Skipping audio transcription.")
                session_prompt += "\n5. Audio Intelligence:\n[Failed - API Key missing]\n"
        
        session_prompt += """
        Analyze the above live technical signals and output the final Market Disruption Battlecard with the required JSON block at the end.
        """
        print(f"[#] Deploying Disruption Radar against target: '{target_company}' with real-time Bright Data feeds...")
    
    # Messaging list for OpenAI SDK format
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": session_prompt}
    ]
    
    max_retries = 3
    attempt = 0
    success = False

    while attempt < max_retries and not success:
        attempt += 1
        print(f"\n[~] Agent Execution Run {attempt}/{max_retries}...")
        
        # Decide which client to use (Groq Primary, Gemini Fallback)
        active_client = grok_client
        active_model = "llama-3.3-70b-versatile"
        
        if not grok_client or (attempt > 1 and gemini_client):
            print("[!] Groq API unavailable or failed. Failing over to Gemini Direct Backend...")
            active_client = gemini_client
            active_model = "gemini-2.5-flash-lite"
        
        if not active_client:
            print("[-] ERROR: No active AI client configured. Set GROK_API_KEY or GEMINI_API_KEY in your .env file.")
            break
        
        try:
            print(f"[+] Dispatching analysis request to {active_model}...")
            response = active_client.chat.completions.create(
                model=active_model,
                messages=messages
            )
            
            reply_text = response.choices[0].message.content
            print("\n[+] --- ANALYSIS COMPLETE --- \n")
            print(reply_text)
            
            # Extract JSON payload and validate
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', reply_text, re.DOTALL | re.IGNORECASE)
            if match:
                json_str = match.group(1)
                json_data = json.loads(json_str, strict=False) # Validate JSON integrity
                
                os.makedirs(os.path.join("web", "data"), exist_ok=True)
                with open(os.path.join("web", "data", "latest_battlecard.json"), "w") as f:
                    json.dump(json_data, f, indent=2)
                
                print("[+] Dashboard data updated at web/data/latest_battlecard.json")
                success = True
                
                # Sync back to Cognee memory
                if COGNEE_AVAILABLE:
                    asyncio.run(setup_cognee_memory(target_company, json_data.get("summary", "")))
            else:
                print("[-] WARNING: Could not extract JSON payload. Engaging Autonomous Healing Loop...")
                messages.append({"role": "assistant", "content": reply_text})
                messages.append({"role": "user", "content": "Execution failed: No valid JSON block found in output. Please analyze your previous step, ensure you follow the JSON schema precisely, and output the strictly formatted JSON block."})
        
        except Exception as e:
            print(f"[-] ERROR encountered: {e}")
            print("[!] Engaging Autonomous Healing Loop...")
            messages.append({"role": "user", "content": f"Execution failed with traceback/error:\n{e}\n\nPlease analyze this traceback, rewrite your logic to bypass the error, and try again to return the final JSON."})

    if not success:
        print("[-] CRITICAL FAILURE: Agent could not heal the pipeline after maximum retries.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OmniSight Agent Runtime")
    parser.add_argument("company_name", help="Target company name")
    parser.add_argument("--audio", help="Path to audio file for Speechmatics intel", default=None)
    parser.add_argument("--audio-url", help="URL to audio file for Speechmatics intel", default=None)
    args = parser.parse_args()
        
    run_analysis(args.company_name, args.audio, args.audio_url)