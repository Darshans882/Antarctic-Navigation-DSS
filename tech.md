# Tech Stack Overview

This project is a full-stack decision-support system for Antarctic navigation, sea-ice monitoring, iceberg forecasting, and route optimization. It combines a Python-based backend for analytics and routing with a React frontend for dashboards and geospatial visualization.

## 1. Application Architecture

### Frontend
- Framework: React 18
- Language: TypeScript
- Build tool: Vite 5
- Styling: Tailwind CSS 3
- Mapping & visualization:
  - Leaflet
  - react-leaflet
  - react-globe.gl
  - Recharts
- Icons: Heroicons
- HTTP client: Axios

### Backend
- Runtime: Python 3.11
- API framework: FastAPI
- ASGI server: Uvicorn
- Validation / settings: Pydantic v2 + pydantic-settings
- ORM: SQLAlchemy
- Database: SQLite by default, with a structure compatible with future PostgreSQL/PostGIS integration

### Core AI / Data / Analytics Layer
- Scientific computing: NumPy, Pandas, Xarray, NetCDF4
- Geospatial processing: GeoPandas, Shapely, PyProj
- Machine learning: scikit-learn, PyTorch
- Data processing: Joblib, Matplotlib, IJSON

### Deployment / Hosting
- Containerization: Docker
- Cloud deployment: Render (backend and static frontend config in render.yaml)
- Frontend hosting: Vercel-ready static build
- Dev workflow: PowerShell launcher scripts for Windows-based local setup

---

## 2. Frontend Stack Details

### Technology choices
The frontend is built in the `frontend/` directory and uses a modern Vite + React setup.

#### Core frontend stack
- React 18.3.1
- TypeScript 5.5.4
- Vite 5.4.2
- Tailwind CSS 3.4.10
- PostCSS + Autoprefixer

#### Why this was chosen
- Fast hot-reloading during development
- Strong TypeScript support for UI state and API contracts
- Clean component-driven development for a dashboard-heavy application
- Tailwind for quick responsive UI design

#### Visualization libraries
- Leaflet + react-leaflet
  - Used for interactive maps, route overlays, and geospatial layers
- react-globe.gl
  - Provides globe-based visualization for Antarctic and ocean monitoring views
- Recharts
  - Used for charts, metrics, and analytics dashboards
- Heroicons
  - Consistent iconography for dashboard actions and status indicators

#### HTTP and API integration
- Axios
  - Calls backend endpoints such as `/api/health`, `/api/sea-ice/*`, `/api/icebergs`, and `/api/routes/optimize`

#### Frontend scripts
From `frontend/package.json`:
- `npm run dev` → local frontend development server
- `npm run build` → production build
- `npm run preview` → preview built app
- `tsc --noEmit` → TypeScript validation

---

## 3. Backend Stack Details

### Core backend stack
- Python 3.11
- FastAPI
- Uvicorn
- Pydantic 2
- SQLAlchemy 2

### Why this was chosen
- FastAPI provides a lightweight, modern REST API with automatic docs
- Pydantic handles validation, settings management, and data contracts
- SQLAlchemy supports DB modeling and future scale-up to relational databases
- Uvicorn is efficient for serving async Python APIs

### Backend structure
The backend code is organized into multiple modules:
- `backend/main.py` → app entry point
- `backend/api/` → REST endpoints
- `backend/database/` → ORM models and DB setup
- `backend/services/` → route and analytics processing
- `backend/ml/` → ML model code
- `backend/navigation/` → geospatial pathfinding and route logic
- `backend/assistant/` → AI assistant integration tools and prompt logic

### API behavior
The backend exposes API routes under `/api`, including:
- health checks
- dataset access
- sea-ice current and forecast data
- iceberg detection / tracking
- route optimization
- AI assistant chat
- analytics summaries

### Documentation generation
FastAPI automatically generates OpenAPI and Swagger docs:
- `/docs`
- `/openapi.json`

---

## 4. Data Science and ML Stack

### Data processing and scientific libraries
- NumPy
- Pandas
- Xarray
- NetCDF4
- IJSON
- Matplotlib

### Geospatial stack
- GeoPandas
- Shapely
- PyProj

These libraries support:
- coastline and land-mask processing
- gridded environmental datasets
- route safety calculations
- Antarctic/ice-region spatial analyses

### Machine learning stack
- scikit-learn
- PyTorch
- joblib

The project includes model-driven workflows for:
- sea-ice forecasting
- iceberg prediction and classification
- route and risk evaluation

### Project model theme
The configuration indicates:
- `SEA_ICE_MODEL = "persistence"`
- `ICEBERG_MODEL = "random_forest"`

This means the system is designed to support operational forecasting with a hybrid mix of time-series and ML-based models.

---

## 5. Database and Persistence Stack

### Default database
- SQLite

### ORM / persistence layer
- SQLAlchemy 2

### Notes
The database layer is intentionally designed as a simple operational starting point and the comments in the code indicate compatibility with future Postgres/PostGIS-based deployment if needed.

This makes the stack ideal for:
- local development
- lightweight demos
- initial deployment without heavy infrastructure

---

## 6. AI and Assistant Stack

The app has an AI assistant layer with configurable providers.

### Supported provider modes
The settings in `backend/config.py` support:
- `auto`
- `openai`
- `anthropic`
- `ollama`
- `none`

### Provider-specific config
- OpenAI: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`
- Anthropic: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
- Ollama: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

### Purpose
The assistant layer is designed to provide contextual, domain-aware responses related to:
- sea-ice interpretation
- iceberg alerts
- route guidance
- analysis summaries

---

## 7. Infra, Deployment, and DevOps Stack

### Local development
- Python virtual environment (`.venv`)
- PowerShell runner scripts: `run.ps1`, `run_accuracy.ps1`

### Containerization
- Dockerfile for backend containerization
- Python 3.11 slim base image
- CPU-specific PyTorch installation via PyTorch index

### Cloud deployment
The project includes deployment configuration in `render.yaml`:
- backend service on Render using Python runtime
- frontend static site on Render
- health check endpoint: `/api/health`
- environment variables configured for real-data mode

### Production posture
The config file is set to:
- `DATA_MODE = "real"`
- `DEMO_MODE = "off"`
- production frontend origin configuration enabled

This indicates the project is intended to operate as a real-data decision-support platform rather than an only-demo prototype.

---

## 8. Development Tooling and Workflow

### Package managers
- Python: pip / requirements.txt + pyproject.toml
- JavaScript: npm

### Testing
- pytest
- httpx

### Linting / validation
- TypeScript compile checks via `tsc --noEmit`
- Vite production build validation
- FastAPI + Python project config for automated testing

### Scripts and automation
The repo includes scripts for:
- preprocessing real data
- evaluating model accuracy
- running the real-data pipeline
- verifying datasets and imports

These support the project’s data-driven workflow and model evaluation lifecycle.

---

## 9. Technology Summary Matrix

| Area | Technologies |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Mapping | Leaflet, react-leaflet, react-globe.gl |
| Charts | Recharts |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| Database | SQLite, SQLAlchemy |
| Data science | NumPy, Pandas, Xarray, NetCDF4 |
| Geospatial | GeoPandas, Shapely, PyProj |
| ML | scikit-learn, PyTorch |
| AI assistant | OpenAI, Anthropic, Ollama-compatible config |
| Deployment | Docker, Render, Vercel-ready static build |
| Testing | pytest, httpx |

---

## 10. Final Assessment

This project uses a modern full-stack architecture centered on:
- FastAPI for the backend API and analytics engine
- React + Vite + Tailwind for an interactive frontend
- Python scientific libraries and ML models for sea-ice and iceberg intelligence
- geospatial libraries for route optimization and environmental analysis
- Docker and Render for cloud deployment

Together, these technologies support a robust decision-support application for Antarctic navigation and operational monitoring.
