# SniffLeads

Lead generation crawler for discovering potential leads from social platforms.

## Features

- **Multi-source crawling**: Reddit (more sources planned)
- **Rate limiting**: Redis-backed per-domain throttling
- **Async processing**: Celery workers for non-blocking crawls
- **REST API**: Full CRUD for leads and crawl management
- **Deduplication**: Automatic lead deduping by profile URL
- **Scheduling**: Automated crawls via Celery Beat

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16 (via Docker)
- Redis 7 (via Docker)

### Development Setup

```bash
# Clone and enter project
cd sniffleads/backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Start databases
docker compose -f infra/compose/docker-compose.dev.yaml up -d postgres redis

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Running Workers

```bash
# Start all services including workers
docker compose -f infra/compose/docker-compose.dev.yaml up -d

# Or rebuild after code changes
docker compose -f infra/compose/docker-compose.dev.yaml up -d --build worker beat
```

### API Access

- Browsable API: http://localhost:8000/api/v1/
- Admin: http://localhost:8000/admin/
- Health check: http://localhost:8000/health/

## Project Structure

```
sniffleads/
├── backend/
│   ├── apps/
│   │   ├── leads/       # Lead model, API
│   │   ├── sources/     # Site configs, crawl jobs
│   │   ├── crawler/     # HTTP client, pipeline
│   │   └── scrapers/    # Reddit, Medium parsers
│   ├── sniffleads/      # Django settings
│   └── scripts/         # Seed scripts
├── infra/
│   ├── compose/         # Docker Compose files
│   └── containers/      # Dockerfiles
└── docs/                # Documentation
```

## Usage

### Create a Site Config

```python
# Django shell
from apps.sources.services import create_site_config
from apps.common.enums import SourceType

config = create_site_config(
    domain="reddit.com",
    name="Reddit - Music Producers",
    source_type=SourceType.REDDIT,
    filters={
        "subreddits": ["WeAreTheMusicMakers", "edmproduction"],
        "sort": "hot",
        "limit": 25,
    },
    requests_per_minute=10,
    max_pages=50,
)
```

### Trigger a Crawl

```python
from apps.crawler.tasks import trigger_crawl_for_config
result = trigger_crawl_for_config(site_config_id=config.id, triggered_by="manual")
```

Or via API:
```bash
curl -X POST http://localhost:8000/api/v1/sources/configs/1/crawl/
```

### View Results

```bash
curl http://localhost:8000/api/v1/leads/
curl http://localhost:8000/api/v1/leads/stats/
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SETTINGS_MODULE` | Settings module | `sniffleads.settings.local` |
| `DATABASE_URL` | PostgreSQL connection | - |
| `CELERY_BROKER_URL` | Redis URL | `redis://localhost:6379/0` |
| `REDIS_URL` | Redis for rate limiting | Same as broker |
| `SECRET_KEY` | Django secret (production) | - |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost` |

## License

MIT