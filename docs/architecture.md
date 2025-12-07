# SniffLeads Architecture

## Overview

SniffLeads is a lead generation platform that crawls social platforms to discover potential leads for outreach. It consists of a Django backend with Celery for async task processing.

## System Components

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  Django     │────▶│ PostgreSQL  │
│  (Browser)  │     │  REST API   │     │  Database   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                          │ Celery Tasks
                          ▼
                   ┌─────────────┐     ┌─────────────┐
                   │   Celery    │────▶│    Redis    │
                   │   Worker    │     │   Broker    │
                   └──────┬──────┘     └─────────────┘
                          │
                          │ HTTP Requests
                          ▼
                   ┌─────────────┐
                   │  External   │
                   │   Sites     │
                   │ (Reddit,etc)│
                   └─────────────┘
```

## Application Structure

```
apps/
├── leads/          # Lead storage and management
├── sources/        # Crawl configuration and job tracking  
├── crawler/        # HTTP client, rate limiting, pipeline
├── scrapers/       # Site-specific parsers (Reddit, Medium)
├── accounts/       # User authentication (future)
└── api/            # REST API routing
```

## Data Flow

1. **Configuration**: User creates `SiteConfig` defining what to crawl
2. **Scheduling**: Celery Beat triggers `schedule_crawl_jobs()` every 15 min
3. **Execution**: Worker picks up job, runs `CrawlPipeline`
4. **Fetching**: HTTP client fetches URLs with rate limiting
5. **Parsing**: Site-specific parser extracts lead data
6. **Storage**: Leads upserted (deduped by profile_url + source_domain)
7. **Logging**: Each request logged to `CrawlLog` for debugging

## Key Design Decisions

### Rate Limiting
- Redis-backed sliding window per domain
- Configurable per SiteConfig (requests_per_minute)
- Fails open if Redis unavailable

### Deduplication
- Unique constraint on (profile_url, source_domain)
- Upsert updates existing leads with fresh data

### Scraper Registry
- Crawlers/parsers registered at app startup
- Easy to add new sources without changing core code

### Async Processing
- All crawls run via Celery (never block web requests)
- Jobs can be triggered via API, scheduler, or manually