# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SemsAi** is a comprehensive real estate platform with:
- **Flutter mobile app** for property search and portfolio management
- **Node.js/Express backend** serving the Flutter app, with MongoDB data
- **Python/FastAPI agents API** for AI-powered property recommendations using LangChain
- **Web scraper** for collecting real estate data from Nawy.com into MongoDB

This is a monorepo with four independent services, each in its own directory, with some shared MongoDB and Redis state.

## Repository Structure

```
SemsAi/
├── semsai-backend/        # Node.js Express API (port 3000)
│   ├── server.js          # Main entry point
│   ├── models/            # Mongoose schemas (User, Developer, Compound, Unit)
│   └── scripts/           # Utility scripts
├── agents-api/            # Python FastAPI agents (port 8000)
│   ├── main.py            # FastAPI app entry
│   ├── graph_definition.py # LangGraph agent workflow definition
│   ├── graph_runner.py    # Graph execution logic
│   ├── agents/            # Individual agent implementations
│   └── api/               # API routes (chat, etc.)
├── SemsAi/                # Flutter mobile app
│   ├── lib/
│   │   ├── core/          # Shared utilities (networking, routing, widgets)
│   │   └── features/      # Feature modules (auth, search, portfolio, etc.)
│   └── pubspec.yaml       # Flutter dependencies
└── nawy-scraper/          # Python Playwright web scraper
    ├── config/            # Settings and environment
    ├── database/          # MongoDB CRUD operations
    ├── scrapers/          # Playwright scrapers (compounds, developers, units)
    ├── utils/             # Data cleaning and export utilities
    └── main.py            # CLI entry point
```

## Quick Start Commands

### semsai-backend (Node.js)
```bash
cd semsai-backend
npm install           # Install dependencies
npm start             # Run server on port 3000
```

### agents-api (Python/FastAPI)
```bash
cd agents-api
pip install -r requirements.txt
cp .env.example .env   # Configure OPENAI_API_KEY, MONGO_URI
python run.py         # Run on port 8000
```

### SemsAi Flutter App
```bash
cd SemsAi
flutter pub get       # Install dependencies
flutter run           # Run on connected device/emulator
```

### nawy-scraper
```bash
cd nawy-scraper
pip install -r requirements.txt
playwright install chromium
python main.py --mode full   # Full scrape (compounds + developers + units)
python main.py --test        # Quick test with 3 items
python main.py --mode compounds --limit 5 --no-headless  # Debug with visible browser
```

## Architecture Patterns

### Data Models & MongoDB
The system uses MongoDB with shared collections accessed by both backends:
- **User**: User accounts, preferences, saved properties
- **Compound**: Real estate compounds/projects (scraped from Nawy.com)
- **Developer**: Developer companies and their portfolios
- **Unit**: Individual property listings with payment plans, pricing
- **MarketMetrics**: Market analysis and trends

The semsai-backend (Express/Mongoose) is the primary interface to MongoDB. The agents-api reads from MongoDB to provide recommendations.

### Integration Points
1. **Flutter app ↔ semsai-backend**: HTTP REST API on port 3000
2. **semsai-backend ↔ agents-api**: Proxies `/conversation/step` → `http://127.0.0.1:8000/agents/step`
3. **agents-api state management**: Redis for session state; MongoDB for persistent property/user data
4. **nawy-scraper → MongoDB**: Upserts property data (compounds, developers, units) with deduplication

### Portfolio/Budget System (semsai-backend)
The backend includes sophisticated portfolio analysis:
- `normalizePortfolioInput()` validates and sanitizes user financial data
- `validatePortfolioInput()` enforces constraints (income > 0, debt ratios, etc.)
- Calculates affordability based on income type (salary/freelance), risk profile (conservative/moderate/aggressive), and existing debts
- Returns recommendations with installment ratios and available budget windows

Key financial inputs: `netMonthlyIncome`, `monthlyFixedExpenses`, `availableCash`, `maxInstallmentRatio`, `creditAccess`, `riskProfile`

### AI Agents System (agents-api)
Uses **LangGraph** for a multi-agent workflow:
- `graph_definition.py`: Defines the agent graph state and node transitions
- `graph_runner.py`: Executes the graph and manages conversation state in Redis
- `/agents/step` endpoint: Takes `{state, user_input}` and returns `{message, state, done}`
- `/run` endpoint: Executes the full agent graph in one call

Agents leverage:
- **OpenAI** for language understanding and recommendations
- **Google Maps API** for location intelligence
- **LangChain** for agent orchestration and tool use
- **Embeddings** (sentence-transformers) for user preference matching

### Flutter Architecture (Clean Code/BLoC)
- **core/**: Shared utilities (networking, routing, constants, widgets)
- **features/**: Feature modules with BLoC pattern
  - Each feature has: `data/` (models, repositories), `presentation/` (UI, BLoC cubits)
- **State management**: BLoC via `flutter_bloc` package
- **Networking**: Custom `api_client.dart` wrapping `http` package
- **Persistence**: `shared_preferences` for local data (auth tokens, preferences)
- **Maps**: `flutter_map` with `latlong2` for location display
- **Caching**: `cached_network_image` for property images

## Environment Configuration

Each service has environment requirements:

**semsai-backend/.env**:
```
MONGO_URI=mongodb+srv://...
PORT=3000
```

**agents-api/.env**:
```
OPENAI_API_KEY=sk-...
MONGO_URI=mongodb+srv://...
REDIS_URL=redis://...
GOOGLE_MAPS_API_KEY=...
```

**nawy-scraper/.env**:
```
MONGO_URI=mongodb+srv://...
HEADLESS=true
DELAY_MIN=3.0
DELAY_MAX=6.0
```

## Key Considerations

### Rate Limiting & Anti-Detection (nawy-scraper)
The scraper includes human-like behavior to avoid detection:
- Random User-Agent rotation
- 3-6 second delays between requests
- Random viewport sizes
- Exponential backoff on errors
- Always test with `--limit 5` before full scrape

### CORS & Production
Currently, `agents-api` allows `CORS allow_origins=["*"]`. This must be tightened for production to accept only the Flutter app domain.

### MongoDB Deduplication
The nawy-scraper **upserts** data (no duplicates). The scraper is safe to run multiple times; it will update existing properties rather than duplicate them.

### Session State Management (agents-api)
User conversations are stored in Redis with session IDs. Each `POST /agents/step` maintains conversational context across multiple turns. Ensure Redis is running before starting agents-api.

### Financial Constraints
The backend's portfolio system enforces:
- `maxInstallmentRatio`: Default 0.4 (40% of income for installments)
- Income type validation (salary vs freelance affects risk assessment)
- Risk profiles constrain investment recommendations

## Testing Approach

- **Flutter**: Use `flutter test` for unit/widget tests
- **semsai-backend**: No test setup currently; manual API testing or use Postman
- **agents-api**: Test chat flows via the `/agents/step` endpoint
- **nawy-scraper**: Use `--test` flag for quick 3-item validation before full runs

## Common Issues & Fixes

**MongoDB Connection Errors**: Ensure MongoDB Atlas connection string is correct and your IP is whitelisted.

**Redis Connection (agents-api)**: Ensure Redis is running and `REDIS_URL` is set. For local development, use `redis://localhost:6379`.

**CORS Errors (Flutter ↔ backends)**: Check that Flask/Express/FastAPI have proper CORS middleware configured.

**Scraper Rate Limiting**: If Nawy.com blocks the scraper, increase `DELAY_MIN` and `DELAY_MAX` in `.env`.

**Flutter Build Errors**: Run `flutter clean && flutter pub get` to resolve dependency issues.

## Deployment Notes

- **semsai-backend**: Deployed as Docker container (Dockerfile in repo)
- **agents-api**: Deployed as Docker container; ensure OpenAI API key is in production secrets
- **Flutter**: Build APK via `flutter build apk` or IPA via `flutter build ios`
- **Scraper**: Runs on-demand or scheduled; ensure MongoDB credentials are in production environment

All services expect production MongoDB Atlas and Redis for state management.
