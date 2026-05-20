# Launchpad Pro - FastAPI + React Architecture

Modern Client-Server architecture for the Resume AI Analyzer application.

## Project Structure

```
launchpad-pro/
├── backend/                    # FastAPI Backend
│   ├── main.py                 # FastAPI app entry point
│   ├── routes/                 # API endpoints
│   │   ├── setup.py            # Resume/Goal management endpoints
│   │   ├── analyze.py          # Analysis endpoints
│   │   └── history.py          # History management endpoints
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Container configuration
├── frontend/                   # React + Vite Frontend
│   ├── src/
│   │   ├── api/                # API client
│   │   ├── components/         # UI components
│   │   ├── hooks/              # React Query hooks
│   │   ├── pages/              # Page components
│   │   ├── store/              # Zustand state management
│   │   └── App.tsx             # Main app component
│   ├── package.json
│   └── Dockerfile              # Container configuration
├── launchpad/                  # Original business logic (PRESERVED)
│   ├── utils/                  # Existing analysis logic
│   ├── data/                   # Local data storage
│   └── requirements.txt        # Python dependencies
├── docker-compose.yml          # Multi-container orchestration
└── README.md                   # This file
```

## Architecture Overview

### Backend (FastAPI)
- **Role**: RESTful API server wrapping existing launchpad logic
- **Features**:
  - Resume upload and management
  - Goal set creation and management
  - Analysis execution
  - History tracking
  - CORS enabled for frontend communication
  
### Frontend (React + Vite)
- **Role**: Modern, interactive UI
- **Features**:
  - Fast development experience with Vite
  - Tailwind CSS for styling (no CSS hacks!)
  - React Query for server state management
  - Zustand for global client state
  - Lucide React for icons
  - Fully typed with TypeScript

### State Management
- **Zustand**: Global client state (selectedResume, currentTab, etc.)
- **React Query**: Server state (API responses, caching)
- **Local Storage**: Persistence (optional)

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Start both backend and frontend
docker-compose up

# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Local Development

#### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the server
python -m uvicorn main:app --reload

# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev

# Frontend will be available at http://localhost:3000
```

## API Endpoints

### Setup Routes (`/api/setup`)
- `POST /upload-resume` - Upload a resume (PDF or DOCX)
- `GET /resumes` - List all resumes
- `DELETE /resume/{resume_name}` - Delete a resume
- `GET /goal-sets` - List all goal sets
- `POST /goal-sets` - Create a new goal set
- `DELETE /goal-sets/{goal_set_id}` - Delete a goal set

### Analysis Routes (`/api/analyze`)
- `POST /run` - Run analysis on resume vs job description
- `POST /score` - Calculate match score
- `POST /suggestions` - Generate improvement suggestions

### History Routes (`/api/history`)
- `GET /` - Get all history entries
- `GET /{entry_id}` - Get specific entry
- `POST /` - Add new history entry
- `DELETE /{entry_id}` - Delete history entry
- `POST /{entry_id}/suggestions` - Save suggestions to entry

## Key Improvements Over Streamlit

✅ **No CSS Hacks** - Tailwind CSS provides professional styling out of the box  
✅ **Better Performance** - React only re-renders changed components (vs Streamlit's full page reload)  
✅ **Real-time Updates** - WebSocket support for live progress feedback  
✅ **Scalability** - Backend and frontend can be deployed independently  
✅ **Type Safety** - Full TypeScript support for both frontend and API  
✅ **Developer Experience** - Vite's lightning-fast HMR (Hot Module Replacement)  
✅ **Modern Stack** - Industry-standard technologies (React, FastAPI, Tailwind)  

## Development Workflow

### Adding a New Feature

1. **Backend**: Add route in `backend/routes/new_feature.py`
2. **Include Route**: Add to `backend/main.py`
3. **Frontend API**: Create wrapper in `frontend/src/api/client.ts`
4. **Frontend Hook**: Add React Query hook in `frontend/src/hooks/index.ts`
5. **Frontend Component**: Create component using hook
6. **Test**: Use Swagger docs (`/docs`) to test backend

### Environment Variables

Create `.env` files in root and backend:

```bash
# backend/.env
API_PORT=8000
OPENAI_API_KEY=sk-...
```

```bash
# frontend/.env.local
VITE_API_URL=http://localhost:8000/api
```

## Deployment

### Production Build

```bash
# Backend
cd backend && docker build -t launchpad-backend .

# Frontend
cd frontend && docker build -t launchpad-frontend .

# Deploy with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### Cloud Deployment Options

- **Backend**: Deploy to Railway, Heroku, AWS Lambda, or DigitalOcean
- **Frontend**: Deploy to Vercel, Netlify, or AWS S3 + CloudFront

## Next Steps

1. ✅ Setup backend with FastAPI routes
2. ✅ Create React frontend with Vite
3. ✅ Connect frontend to backend API
4. ⏳ Migrate existing Streamlit logic to FastAPI
5. ⏳ Update history tab to display suggestions
6. ⏳ Add real-time analysis progress
7. ⏳ Implement user authentication
8. ⏳ Add PDF export of analysis results
9. ⏳ Setup CI/CD pipeline

## Troubleshooting

### CORS Errors
- Backend should be running on `localhost:8000`
- Frontend should be running on `localhost:3000`
- CORS middleware is configured in `backend/main.py`

### API Calls Not Working
- Check that backend is running: `curl http://localhost:8000/health`
- Verify CORS headers in browser DevTools
- Check API endpoint in `frontend/src/api/client.ts`

### Vite Hot Reload Not Working
- Restart `npm run dev`
- Clear browser cache
- Check file changes are saved

## License

Launchpad © 2026
