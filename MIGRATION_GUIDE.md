# Launchpad Architecture Transformation

This directory contains the complete modernized architecture for Launchpad, transitioning from Streamlit to FastAPI + React.

## What Changed?

### Before (Streamlit)
- **Monolithic** single-file architecture
- **Full-page reloads** on every interaction
- **CSS hacks** with unsafe_allow_html=True
- **Limited scalability** - frontend and logic tightly coupled
- **Hard to customize** UI without deep Streamlit knowledge

### After (FastAPI + React)
- **Decoupled** client-server architecture
- **Component-based** React with efficient re-rendering
- **Professional styling** with Tailwind CSS (no hacks!)
- **Scalable** - backend and frontend deployed independently
- **Modern stack** - React, FastAPI, TypeScript, Tailwind

## Directory Overview

### `/backend`
FastAPI-based REST API that wraps the existing `launchpad/utils` logic.
- **main.py** - FastAPI app initialization and CORS setup
- **routes/** - API endpoint handlers
  - `setup.py` - Resume/Goal management
  - `analyze.py` - Analysis endpoints
  - `history.py` - History tracking
- **requirements.txt** - Python dependencies
- **Dockerfile** - Container image

### `/frontend`
React + Vite modern web application with Tailwind CSS styling.
- **src/api/client.ts** - Axios wrapper for API calls
- **src/components/UI.tsx** - Reusable UI components
- **src/hooks/index.ts** - React Query hooks for server state
- **src/store/index.ts** - Zustand for global client state
- **src/pages/** - Full page components
  - `Setup.tsx` - Resume/Goal management UI
  - `Analyze.tsx` - Analysis interface
  - `History.tsx` - History display
- **src/App.tsx** - Main application shell with tab navigation
- **tailwind.config.js** - Styling configuration
- **vite.config.ts** - Vite build configuration
- **package.json** - Node.js dependencies

### `/launchpad` (PRESERVED)
Original business logic remains untouched:
- **utils/** - All analysis, matching, and scoring logic
- **data/** - Local JSON storage
- **requirements.txt** - Python dependencies

## How to Use

### Local Development

1. **Terminal 1 - Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

2. **Terminal 2 - Frontend**
```bash
cd frontend
npm install
npm run dev
```

3. **Access the app**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs

### Docker Deployment

```bash
docker-compose up
```

## Technology Stack

| Layer | Tech | Purpose |
|-------|------|---------|
| Frontend | React 18 | UI library |
| Build | Vite | Fast bundler & dev server |
| Styling | Tailwind CSS | Utility-first styling |
| State (Client) | Zustand | Global state management |
| State (Server) | React Query | API caching & sync |
| HTTP | Axios | API client |
| Icons | Lucide React | Icon library |
| Backend | FastAPI | Python web framework |
| ASGI | Uvicorn | Server |
| Types | Pydantic | Data validation |
| Language | TypeScript | Type-safe frontend |
| Python | 3.11 | Backend runtime |

## Key Features of New Architecture

✨ **Type-Safe API Integration**
- Shared Pydantic models between backend and TypeScript frontend
- Full TypeScript coverage

🎨 **Professional UI**
- Tailwind CSS provides polished, responsive design
- No custom CSS hacks needed
- Lucide React for beautiful icons

⚡ **Performance**
- React's efficient component re-rendering
- React Query handles caching & request deduplication
- Vite's instant HMR for development

📊 **State Management**
- Zustand for simple, performant global state
- React Query for server-synced state
- Clear separation of concerns

🚀 **Scalability**
- Backend and frontend are independent services
- Easy to add new API endpoints
- Easy to add new React components
- Can be containerized and deployed separately

## Migration Path

The existing `launchpad/utils` logic is preserved and now used as a library by the FastAPI backend:

```python
# Before (Streamlit)
from launchpad.utils.matcher import analyze_resume_vs_goal

# After (FastAPI)
@app.post("/api/analyze/run")
async def perform_analysis(...):
    result = analyze_resume_vs_goal(...)  # Same logic!
    return result
```

This allows gradual migration - existing Python logic works unchanged!

## Next Phase: Enhancements

With this modern architecture, you can now easily add:

- 🔐 User authentication & multi-tenant support
- 💾 PostgreSQL database for permanent storage
- 🔄 WebSockets for real-time analysis progress
- 📧 Email reports of analyses
- 🤖 Advanced AI features via separate service
- 📱 Mobile app (using React Native with same API)
- 🔌 Third-party integrations (LinkedIn, etc.)

All without the constraints of Streamlit's architecture!

## Questions?

Refer to:
- **Frontend Development**: See `frontend/` structure
- **Backend Development**: See `backend/` structure  
- **Full Architecture**: See `../ARCHITECTURE.md`
- **API Reference**: Navigate to http://localhost:8000/docs after starting backend
