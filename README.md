# Netflix Data Explorer

A full-stack web application for exploring and analyzing **8,807 Netflix Movies & TV Shows** with interactive charts, smart filtering, year-over-year analysis, authentication, and PDF export.

**MindX Python K1 - Final Project**

---

## Features

- **Browse & Search** - Filter titles by type, rating, genre, country, year range with real-time search
- **Interactive Charts** - 12 Chart.js visualizations (donut, bar, line, stacked) for data insights
- **Year-over-Year Analysis** - Compare any two years side-by-side with delta indicators
- **Genre & Country Trends** - Track how content strategy evolved over time
- **PDF Export** - Download filtered results as a formatted PDF report
- **Authentication** - Session-based login + API key protection
- **Detail Modal** - Full title info with cast, director, genres, and description
- **Responsive Design** - Cinematic dark theme that works on all devices
- **Loading States** - Skeleton shimmer cards, error handling with retry, empty state guidance

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python Flask |
| Data Processing | Pandas |
| Frontend | HTML / CSS / JavaScript (vanilla) |
| Charts | Chart.js |
| PDF Generation | fpdf2 |
| Auth | Flask Sessions + API Key |

---

## Quick Setup

```bash
# 1. Clone the repo
git clone git@github.com:leenguyen17/Mindx_Python_FinalTest.git
cd Mindx_Python_FinalTest

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Run
python app.py
```

Open **http://localhost:5000** and login.

> For detailed setup instructions, see [docs/setup-guide.md](docs/setup-guide.md)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | Login page |
| POST | `/login` | Authenticate user |
| GET | `/logout` | Clear session |
| GET | `/api/titles` | Filtered, paginated title list |
| GET | `/api/titles/<id>` | Single title detail |
| GET | `/api/filters` | Available filter options |
| GET | `/api/stats` | Aggregated statistics |
| GET | `/api/analysis` | Year-over-year analysis + comparison |
| GET | `/api/export/pdf` | Export filtered results as PDF |

All `/api/*` endpoints require authentication (session) and API key (`X-API-Key` header).

---

## Project Structure

```
.
├── app.py                  # Flask backend (API + auth + PDF export)
├── config.py               # Configuration (loads from .env)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── data/
│   └── netflix_titles.csv  # Dataset (8,807 titles)
├── static/
│   ├── css/style.css       # Cinematic dark theme
│   └── js/
│       ├── api.js          # API client with auth
│       ├── components.js   # UI render functions
│       ├── charts.js       # Chart.js wrappers
│       └── app.js          # State management
├── templates/
│   ├── login.html          # Login page
│   └── index.html          # Main SPA shell
├── presentation/
│   └── slides.html         # Presentation slides
└── docs/
    └── setup-guide.md      # Detailed setup instructions
```

---

## Dataset

Source: Netflix Movies and TV Shows dataset
- **8,807 titles** (6,131 Movies + 2,676 TV Shows)
- **12 columns**: show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description
- **Year range**: 1925 - 2021
