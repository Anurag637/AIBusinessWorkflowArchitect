# AI Business Workflow Architect

An agentic AI system that converts natural-language business requirements into validated, simulated, and executable business workflows.

## Architecture

```
User → Next.js UI → FastAPI → LangGraph Agents → Tool Registry → Execution Engine
                                    ↓
                              PostgreSQL + Qdrant
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Run with Docker Compose

```bash
# Clone the repository
git clone <repo-url>
cd ai-business-workflow-architect

# Copy environment variables
cp .env.example .env

# Start all services
docker compose up --build
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Qdrant**: http://localhost:6333

### Local Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js + TypeScript |
| Backend | Python + FastAPI |
| Agent Orchestration | LangGraph |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Vector DB | Qdrant |
| LLM | Configurable provider |
| Infrastructure | Docker + Docker Compose |

## Project Structure

```
ai-business-workflow-architect/
├── backend/          # FastAPI + LangGraph agents
├── frontend/         # Next.js + TypeScript UI
├── knowledge/        # Company policy documents
├── docs/             # Architecture documentation
├── tests/            # Integration tests
├── docker-compose.yml
├── .env.example
└── README.md
```

## Documentation

- [Architecture](docs/architecture.md)
- [Product Requirements](docs/product-requirements.md)
- [API Design](docs/api-design.md)
- [Workflow Schema](docs/workflow-schema.md)
- [Security Model](docs/security-model.md)
- [Implementation Plan](docs/implementation-plan.md)

## License

MIT
