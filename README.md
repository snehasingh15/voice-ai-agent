# <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/microphone-duotone.svg" width="32" align="center" /> Voice AI Agent

A full-stack voice AI application with a FastAPI backend (WebSocket-based voice pipeline) and a React/Vite frontend.

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/folders-duotone.svg" width="24" align="center" /> Project Structure

```
voice_ai/
├── backend/      # FastAPI + Python voice pipeline
└── frontend/     # React + Vite UI
```

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/gear-duotone.svg" width="24" align="center" /> Prerequisites

- **Python** 3.10+
- **Node.js** 18+ and **npm**

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/wrench-duotone.svg" width="24" align="center" /> Backend Setup

### 1. Navigate to the backend directory

```bash
cd backend
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example env file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DEEPGRAM_API_KEY=your_deepgram_api_key
GROQ_API_KEY=your_groq_api_key
MONGODB_USERNAME=your_mongo_username
MONGODB_PASSWORD=your_mongo_password
MONGODB_URI=your_mongodb_connection_string
MONGODB_DB_NAME=voice_ai_db
GEMINI_API_KEY=your_gemini_api_key
ADMIN_PASSWORD=your_admin_password
```

### 5. Start the backend server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: **http://localhost:8000**

- WebSocket endpoint: `ws://localhost:8000/ws/session`
- Image upload: `POST http://localhost:8000/api/upload-image`
- Analytics: `http://localhost:8000/analytics/...`

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/paint-brush-duotone.svg" width="24" align="center" /> Frontend Setup

### 1. Navigate to the frontend directory

```bash
cd frontend
```

### 2. Install dependencies

```bash
npm install
```

### 3. Start the development server

```bash
npm run dev
```

The app will be available at: **http://localhost:5173**

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/rocket-launch-duotone.svg" width="24" align="center" /> Running Both Together

Open two terminal windows/tabs and run each service simultaneously:

**Terminal 1 — Backend:**
```bash
cd backend
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/terminal-window-duotone.svg" width="24" align="center" /> Other Frontend Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start dev server with hot reload |
| `npm run build` | Build for production |
| `npm run preview` | Preview the production build |
| `npm run lint` | Run linter (oxlint) |

---

## <img src="https://raw.githubusercontent.com/phosphor-icons/core/main/assets/duotone/key-duotone.svg" width="24" align="center" /> Required API Keys

| Key | Where to get it |
|---|---|
| `DEEPGRAM_API_KEY` | [deepgram.com](https://deepgram.com) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `MONGODB_URI` | [mongodb.com/atlas](https://www.mongodb.com/atlas) |
