# Netflix Data Explorer - Setup Guide

Step-by-step instructions to set up and run the project locally.

---

## Prerequisites

- **Python 3.8+** installed ([python.org/downloads](https://www.python.org/downloads/))
- **pip** (comes with Python)
- **Git** (optional, for cloning)

Verify:
```bash
python3 --version   # Should show 3.8 or higher
pip3 --version
```

---

## Step 1: Get the Source Code

**Option A**: Clone from GitHub
```bash
git clone git@github.com:leenguyen17/Mindx_Python_FinalTest.git
cd Mindx_Python_FinalTest
```

**Option B**: Download and extract the ZIP from GitHub.

---

## Step 2: Create Virtual Environment

```bash
python3 -m venv venv
```

Activate the virtual environment:

- **macOS / Linux**:
  ```bash
  source venv/bin/activate
  ```
- **Windows**:
  ```bash
  venv\Scripts\activate
  ```

You should see `(venv)` in your terminal prompt.

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
| Package | Purpose |
|---------|---------|
| Flask | Web framework / REST API |
| Pandas | Data loading and processing |
| python-dotenv | Environment variable management |
| fpdf2 | PDF report generation |

---

## Step 4: Configure Environment Variables

Create a `.env` file in the project root (or copy the example):

```bash
cp .env.example .env
```

Edit `.env` with your preferred values:
```
SECRET_KEY=your-secret-key-here
API_KEY=your-api-key-here
APP_USERNAME=admin
APP_PASSWORD=your-password-here
```

---

## Step 5: Verify Data File

Make sure the CSV file exists:
```bash
ls data/netflix_titles.csv
```

The file should contain 8,807 rows of Netflix titles.

---

## Step 6: Run the Application

```bash
python app.py
```

You should see:
```
  Loaded 8807 titles from CSV
  Filters: 42 genres, 748 countries
  Login: username=admin
 * Running on http://127.0.0.1:5000
```

---

## Step 7: Open in Browser

Navigate to: **http://localhost:5000**

1. You will see the **Login page**
2. Enter your username and password (from `.env`)
3. Explore the Netflix data!

---

## Step 8: Explore Features

| Feature | How to Use |
|---------|------------|
| **Browse** | Use filter dropdowns and search bar to find titles |
| **Detail Modal** | Click any title card to see full details |
| **Statistics** | Click "Statistics" tab to see overview charts |
| **Analysis** | Click "Analysis" tab for year-over-year trends and comparisons |
| **Year Comparison** | Select two years and click "Compare" for side-by-side analysis |
| **Export PDF** | Click "Export PDF" button to download filtered results |
| **Logout** | Click "Logout" in the header |

---

## Presentation Slides

Open `presentation/slides.html` directly in your browser. Navigate with:
- Arrow keys (up/down or left/right)
- Spacebar (next slide)
- Scroll

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Make sure venv is activated: `source venv/bin/activate` |
| Port 5000 in use | Change port in `app.py`: `app.run(port=5001)` |
| CSV not found | Verify `data/netflix_titles.csv` exists in the project root |
| Login fails | Check username/password in `.env` file |

---

## Stopping the Server

Press `Ctrl + C` in the terminal to stop the Flask server.

To deactivate the virtual environment:
```bash
deactivate
```
