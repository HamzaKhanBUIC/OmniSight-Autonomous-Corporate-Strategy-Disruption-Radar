# OmniSight: Autonomous Corporate Strategy & Disruption Radar

### 💡 Inspiration
Corporate espionage and competitive strategy are stuck in the dark ages. Today’s strategy teams, venture capitalists, and enterprise executives spend days manually scraping Google for competitor moves, listening to hours of boring earnings calls, and building static intelligence reports that are outdated the moment they are exported. We realized that in the age of autonomous agents, this process shouldn't take days—it should take minutes. We built OmniSight to be the ultimate competitive disruption radar, allowing teams to gain an unfair, real-time advantage over their competitors. 

### 🚀 What it does
OmniSight is an enterprise-grade, autonomous corporate intelligence dashboard. Instead of manual research, users simply input a competitor's name and attach relevant audio (such as a leaked internal all-hands, a keynote, or an earnings call). OmniSight immediately deploys concurrent, autonomous AI agents to build a comprehensive, real-time battlecard. 

The dashboard provides executives with:
- **Real-Time Benchmarking**: Dual-layered radar charts visualizing market positioning.
- **Actionable Intelligence**: Live tracking of "Hiring Velocity", "Pricing Changes", and "Sentiment/Outages".
- **Audio Intelligence Extraction**: Interactive, chat-bubble style transcripts identifying key strategic shifts from raw audio.
- **Historical Context**: An evolving memory graph that ensures each subsequent scan builds upon past intelligence.

### ⚙️ How we built it
We architected OmniSight for speed, scale, and deep intelligence, heavily leveraging our sponsor's APIs:

* **Bright Data (SERP API & Web Unlocker)**: This is our real-time pulse. We use Bright Data to execute high-speed, parallel Google searches to detect live changes in a competitor's hiring, pricing, and public sentiment. The Web Unlocker is critical for deep-scraping top URLs and effortlessly bypassing CAPTCHAs that normally block competitive analysis.
* **Speechmatics (Batch Async API)**: For unstructured audio ingestion, Speechmatics is our ear to the ground. We feed offline audio files or direct media URLs into the Batch Async API to achieve highly accurate, speaker-diarized transcripts and strategic keyword extraction.
* **Cognee (Agent Graph Memory)**: Intelligence is useless without memory. We integrated Cognee to construct an Agent Graph Memory. Every competitor scanned is committed to this graph, giving our agents persistent historical context. If a competitor pivots next month, OmniSight remembers their stance from today.
* **Google Gemini & Groq (Llama 3)**: Acting as the cognitive engine, these LLMs synthesize the massive influx of live web data and diarized audio transcripts into a structured JSON battlecard, ready for UI consumption.
* **Tech Stack**: We built the backend using Python with `asyncio` for parallel agent execution. The frontend is a vanilla JS and HTML/Tailwind CSS masterpiece, featuring glassmorphism design and dynamic Chart.js visualizations.

### 🛑 Challenges we ran into
Handling massive, unstructured, and disparate data streams simultaneously is hard. Initially, our sequential data pipeline caused scans to take over 5 minutes, resulting in frequent timeouts and a poor user experience. We had to completely refactor our Python backend to use `asyncio` and parallel processing. By deploying concurrent agents for SERP scraping, Deep-URL parsing, and audio processing, we slashed our processing time significantly. We also built a live terminal UI in the backend to monitor these parallel data streams and ensure no silent failures during execution.

### 🔮 What's next for OmniSight
OmniSight is ready to move from a hackathon prototype to a $10M B2B SaaS startup. Next, we plan to:
1. **Automated Alerting**: Push notifications via Slack/Teams when a competitor significantly alters their pricing or launches a new product.
2. **Deep Social Listening**: Integrate X/Twitter and LinkedIn scraping to track executive departures and sentiment shifts in real-time.
3. **Predictive Modeling**: Use our Cognee memory graph to predict a competitor's next move before they make it.
