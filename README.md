# 👁️ OmniSight
> **Autonomous Corporate Strategy & Disruption Radar**

![OmniSight Banner](https://via.placeholder.com/1200x400/0f172a/38bdf8?text=OmniSight+-+Autonomous+Competitive+Intelligence)

OmniSight is an enterprise-grade corporate intelligence dashboard built for executives, venture capitalists, and strategy teams. Stop manually Googling your competitors or listening to hours of earnings calls. Simply enter a competitor's name, attach an audio file, and let OmniSight deploy autonomous AI agents to build a real-time, deep-dive intelligence battlecard. 

## ✨ Features

- **⚡ Live Competitive Scraping**: Instantly tracks "Hiring Velocity", "Pricing Changes", and "Sentiment/Outages".
- **🎙️ Audio Intelligence**: Ingests offline audio or YouTube links for highly accurate speaker diarization and strategic keyword extraction.
- **🧠 Agent Graph Memory**: Every scan is saved to a knowledge graph, giving the AI persistent historical context for future benchmarking.
- **📊 Executive Dashboard**: Beautiful, glassmorphism UI featuring dual-layered radar charts and chat-bubble transcripts for rapid insights.
- **🚀 Concurrent Agent Architecture**: Parallel asynchronous execution ensures deep-dive intelligence is delivered in seconds, not hours.

## 🏗️ Architecture & Tech Stack

OmniSight represents the cutting edge of AI agent orchestration, built utilizing industry-leading tools:

### Core Infrastructure
* **Backend**: Python (Asyncio for parallel agent orchestration)
* **Frontend**: Vanilla JS, HTML, Tailwind CSS, Chart.js
* **LLM Cognitive Engine**: Google Gemini / Groq (Llama 3) for synthesizing complex web data and transcripts into structured JSON.

### Sponsor Technologies
* **🌐 Bright Data (SERP API & Web Unlocker)**: Executes live, parallel searches to capture market shifts while utilizing the Web Unlocker to deep-scrape URLs and bypass CAPTCHAs.
* **🗣️ Speechmatics (Batch Async API)**: Powers our audio ingestion pipeline, providing industry-leading speaker diarization and transcription from raw files or direct URLs.
* **🕸️ Cognee**: Constructs our Agent Graph Memory, ensuring the platform retains historical context and relationships between competitors across multiple scans.

## 🚀 How to Run Locally

### Prerequisites
- Python 3.9+
- API Keys for Bright Data, Speechmatics, Cognee, and Google Gemini / Groq.

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/omnisight.git
   cd omnisight
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   BRIGHT_DATA_API_KEY=your_key_here
   SPEECHMATICS_API_KEY=your_key_here
   COGNEE_API_KEY=your_key_here
   GEMINI_API_KEY=your_key_here
   GROQ_API_KEY=your_key_here
   ```

4. **Run the Application**
   ```bash
   python server.py
   ```
   
5. **Access the Dashboard**
   Open your browser and navigate to `http://localhost:8000` (or the port specified in your terminal) to view the OmniSight dashboard.

---
*Built with ❤️ for the GTM Intelligence & Market Intelligence Track.*
