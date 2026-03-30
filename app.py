"""Netflix Data Explorer - Flask Backend API"""

import io
import base64
import functools
from datetime import datetime

import pandas as pd
from flask import (
    Flask, jsonify, request, render_template,
    session, redirect, url_for, send_file
)
from fpdf import FPDF

import config

# ─── App Setup ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ─── Load & Pre-process Data ─────────────────────────────────────────────────

df = pd.read_csv(config.CSV_PATH)

# Clean whitespace in date_added
df['date_added'] = df['date_added'].str.strip()

# Fill NaN for text columns
for col in ['director', 'cast', 'country', 'date_added', 'rating', 'duration']:
    df[col] = df[col].fillna('')

# Parse date_added
df['date_parsed'] = pd.to_datetime(df['date_added'], format='mixed', errors='coerce')

# Pre-compute filter options
def explode_unique(series, sep=', '):
    """Split comma-separated values and return sorted unique list."""
    return sorted(
        series.dropna()
        .str.split(sep)
        .explode()
        .str.strip()
        .loc[lambda s: s != '']
        .unique()
        .tolist()
    )

FILTER_OPTIONS = {
    'types': sorted(df['type'].unique().tolist()),
    'ratings': sorted(df['rating'].loc[df['rating'] != ''].unique().tolist()),
    'genres': explode_unique(df['listed_in']),
    'countries': explode_unique(df['country']),
    'year_min': int(df['release_year'].min()),
    'year_max': int(df['release_year'].max()),
}

# ─── Auth Decorators ──────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key:
            return jsonify({'error': 'Missing API key'}), 401
        if api_key != config.API_KEY:
            return jsonify({'error': 'Invalid API key'}), 403
        return f(*args, **kwargs)
    return decorated


# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if session.get('authenticated'):
            return redirect(url_for('index'))
        return render_template('login.html')

    username = request.form.get('username', '')
    password = request.form.get('password', '')

    if username == config.APP_USERNAME and password == config.APP_PASSWORD:
        session['authenticated'] = True
        session['username'] = username
        return redirect(url_for('index'))

    return render_template('login.html', error='Invalid username or password')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─── Page Routes ──────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return render_template('index.html', api_key=config.API_KEY)


# ─── Helper: Apply Filters ───────────────────────────────────────────────────

def apply_filters(dataframe):
    """Apply query param filters to the dataframe, return filtered copy."""
    filtered = dataframe.copy()

    # Type filter
    type_filter = request.args.get('type', '').strip()
    if type_filter:
        filtered = filtered[filtered['type'] == type_filter]

    # Rating filter
    rating = request.args.get('rating', '').strip()
    if rating:
        filtered = filtered[filtered['rating'] == rating]

    # Genre filter
    genre = request.args.get('genre', '').strip()
    if genre:
        filtered = filtered[filtered['listed_in'].str.contains(genre, case=False, na=False)]

    # Country filter
    country = request.args.get('country', '').strip()
    if country:
        filtered = filtered[filtered['country'].str.contains(country, case=False, na=False)]

    # Year range
    year_min = request.args.get('year_min', type=int)
    year_max = request.args.get('year_max', type=int)
    if year_min is not None:
        filtered = filtered[filtered['release_year'] >= year_min]
    if year_max is not None:
        filtered = filtered[filtered['release_year'] <= year_max]

    # Search
    search = request.args.get('search', '').strip()
    if search:
        mask = (
            filtered['title'].str.contains(search, case=False, na=False) |
            filtered['director'].str.contains(search, case=False, na=False) |
            filtered['cast'].str.contains(search, case=False, na=False) |
            filtered['description'].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    return filtered


def df_to_records(dataframe):
    """Convert dataframe to list of dicts with NaN/empty replaced by None."""
    cols = ['show_id', 'type', 'title', 'director', 'cast', 'country',
            'date_added', 'release_year', 'rating', 'duration', 'listed_in', 'description']
    records = dataframe[cols].to_dict(orient='records')
    for rec in records:
        for key, val in rec.items():
            if val is None or (isinstance(val, float) and pd.isna(val)) or val == '':
                rec[key] = None
            elif isinstance(val, (int, float)):
                rec[key] = int(val) if val == int(val) else val
    return records


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route('/api/titles')
@login_required
@require_api_key
def api_titles():
    try:
        filtered = apply_filters(df)

        # Sort
        sort_by = request.args.get('sort_by', 'date_added')
        sort_order = request.args.get('sort_order', 'desc')
        valid_sorts = {'title': 'title', 'release_year': 'release_year', 'date_added': 'date_parsed'}
        sort_col = valid_sorts.get(sort_by, 'date_parsed')
        filtered = filtered.sort_values(sort_col, ascending=(sort_order == 'asc'), na_position='last')

        # Pagination
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
        total = len(filtered)
        total_pages = max(1, -(-total // per_page))  # ceil division
        start = (page - 1) * per_page
        end = start + per_page

        titles = df_to_records(filtered.iloc[start:end])

        return jsonify({
            'titles': titles,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/titles/<show_id>')
@login_required
@require_api_key
def api_title_detail(show_id):
    try:
        match = df[df['show_id'] == show_id]
        if match.empty:
            return jsonify({'error': 'Title not found'}), 404
        record = df_to_records(match)[0]
        return jsonify(record)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/filters')
@login_required
@require_api_key
def api_filters():
    return jsonify(FILTER_OPTIONS)


@app.route('/api/stats')
@login_required
@require_api_key
def api_stats():
    try:
        stats = {
            'total_titles': len(df),
            'total_movies': int((df['type'] == 'Movie').sum()),
            'total_tv_shows': int((df['type'] == 'TV Show').sum()),
            'by_rating': df['rating'].loc[df['rating'] != ''].value_counts().to_dict(),
            'by_year': df['release_year'].value_counts().sort_index().to_dict(),
            'by_country_top10': (
                df['country'].str.split(', ')
                .explode().str.strip()
                .loc[lambda s: s != '']
                .value_counts().head(10).to_dict()
            ),
            'by_genre_top10': (
                df['listed_in'].str.split(', ')
                .explode().str.strip()
                .value_counts().head(10).to_dict()
            ),
            'movies_vs_tvshows_by_year': {},
            'added_by_year_month': {},
        }

        # Movies vs TV Shows by year
        pivot = df.groupby(['release_year', 'type']).size().unstack(fill_value=0)
        for year in pivot.index:
            stats['movies_vs_tvshows_by_year'][int(year)] = {
                'Movie': int(pivot.loc[year].get('Movie', 0)),
                'TV Show': int(pivot.loc[year].get('TV Show', 0)),
            }

        # Added by year-month
        valid_dates = df[df['date_parsed'].notna()].copy()
        valid_dates['ym'] = valid_dates['date_parsed'].dt.to_period('M').astype(str)
        stats['added_by_year_month'] = valid_dates['ym'].value_counts().sort_index().to_dict()

        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Analysis API ─────────────────────────────────────────────────────────────

@app.route('/api/analysis')
@login_required
@require_api_key
def api_analysis():
    try:
        result = {}

        # --- Year-over-Year Growth ---
        yearly = df['release_year'].value_counts().sort_index()
        yoy = {}
        prev = None
        for year, count in yearly.items():
            entry = {'count': int(count)}
            if prev is not None:
                entry['change_pct'] = round((count - prev) / prev * 100, 1) if prev > 0 else 0
            yoy[int(year)] = entry
            prev = count
        result['yoy_growth'] = yoy

        # --- Movies vs TV Shows share by year ---
        type_by_year = df.groupby(['release_year', 'type']).size().unstack(fill_value=0)
        type_share = {}
        for year in type_by_year.index:
            row = type_by_year.loc[year]
            total = row.sum()
            type_share[int(year)] = {
                'Movie': int(row.get('Movie', 0)),
                'TV Show': int(row.get('TV Show', 0)),
                'movie_pct': round(row.get('Movie', 0) / total * 100, 1) if total > 0 else 0,
                'tvshow_pct': round(row.get('TV Show', 0) / total * 100, 1) if total > 0 else 0,
            }
        result['type_share_by_year'] = type_share

        # --- Genre trends (top 10 genres, last 7 years) ---
        top_genres = (
            df['listed_in'].str.split(', ').explode().str.strip()
            .value_counts().head(10).index.tolist()
        )
        genre_df = df[['release_year', 'listed_in']].copy()
        genre_df = genre_df[genre_df['release_year'] >= df['release_year'].max() - 6]
        genre_trends = {}
        for genre in top_genres:
            mask = genre_df['listed_in'].str.contains(genre, case=False, na=False)
            counts = genre_df[mask].groupby('release_year').size()
            genre_trends[genre] = {int(y): int(c) for y, c in counts.items()}
        result['genre_trends'] = genre_trends

        # --- Rating distribution shift (last 7 years) ---
        recent = df[df['release_year'] >= df['release_year'].max() - 6]
        rating_by_year = recent.groupby(['release_year', 'rating']).size().unstack(fill_value=0)
        result['rating_by_year'] = {
            int(year): {r: int(v) for r, v in row.items() if v > 0}
            for year, row in rating_by_year.iterrows()
        }

        # --- Average movie duration by year ---
        movies = df[df['type'] == 'Movie'].copy()
        movies['duration_min'] = movies['duration'].str.extract(r'(\d+)').astype(float)
        avg_dur = movies.groupby('release_year')['duration_min'].mean()
        result['avg_movie_duration'] = {int(y): round(d, 1) for y, d in avg_dur.items() if pd.notna(d)}

        # --- Top countries by year (last 7 years) ---
        top_countries = (
            df['country'].str.split(', ').explode().str.strip()
            .loc[lambda s: s != '']
            .value_counts().head(5).index.tolist()
        )
        country_df = df[['release_year', 'country']].copy()
        country_df = country_df[country_df['release_year'] >= df['release_year'].max() - 6]
        country_trends = {}
        for c in top_countries:
            mask = country_df['country'].str.contains(c, case=False, na=False)
            counts = country_df[mask].groupby('release_year').size()
            country_trends[c] = {int(y): int(v) for y, v in counts.items()}
        result['country_trends'] = country_trends

        # --- Comparison Mode ---
        year1 = request.args.get('year1', type=int)
        year2 = request.args.get('year2', type=int)
        if year1 and year2:
            def year_snapshot(yr):
                subset = df[df['release_year'] == yr]
                return {
                    'total': len(subset),
                    'movies': int((subset['type'] == 'Movie').sum()),
                    'tv_shows': int((subset['type'] == 'TV Show').sum()),
                    'top_genres': (
                        subset['listed_in'].str.split(', ').explode().str.strip()
                        .value_counts().head(5).to_dict()
                    ),
                    'top_countries': (
                        subset['country'].str.split(', ').explode().str.strip()
                        .loc[lambda s: s != '']
                        .value_counts().head(5).to_dict()
                    ),
                    'ratings': subset['rating'].value_counts().to_dict(),
                }

            snap1 = year_snapshot(year1)
            snap2 = year_snapshot(year2)
            result['comparison'] = {
                'year1': {'year': year1, **snap1},
                'year2': {'year': year2, **snap2},
                'delta': {
                    'total': snap2['total'] - snap1['total'],
                    'movies': snap2['movies'] - snap1['movies'],
                    'tv_shows': snap2['tv_shows'] - snap1['tv_shows'],
                }
            }

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── PDF Export ───────────────────────────────────────────────────────────────

@app.route('/api/export/pdf')
@login_required
@require_api_key
def api_export_pdf():
    try:
        filtered = apply_filters(df)
        total = len(filtered)

        def safe_text(text):
            if not text:
                return ''
            replacements = {
                '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
                '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00e9': 'e',
                '\u00e1': 'a', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
                '\u00f1': 'n', '\u00fc': 'u', '\u00e8': 'e', '\u00e0': 'a',
            }
            for k, v in replacements.items():
                text = text.replace(k, v)
            return text.encode('latin-1', errors='replace').decode('latin-1')

        # Collect active filters for display
        filters_applied = []
        for param in ['type', 'rating', 'genre', 'country', 'year_min', 'year_max', 'search']:
            val = request.args.get(param, '').strip()
            if val:
                filters_applied.append(f'{param}: {val}')

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ── Title Page ──
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 28)
        pdf.ln(50)
        pdf.cell(0, 15, 'Netflix Data Explorer', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 16)
        subtitle = 'Filtered Data Analysis' if filters_applied else 'Full Dataset Analysis'
        pdf.cell(0, 10, subtitle, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(10)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.cell(0, 8, f'Titles analyzed: {total:,}', align='C', new_x='LMARGIN', new_y='NEXT')
        if filters_applied:
            pdf.ln(3)
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 8, safe_text(f'Filters: {" | ".join(filters_applied)}'), align='C', new_x='LMARGIN', new_y='NEXT')

        # ── Page 2: Overview Summary ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Overview', safe_text)
        n_movies = int((filtered['type'] == 'Movie').sum())
        n_tv = int((filtered['type'] == 'TV Show').sum())
        movie_pct = round(n_movies / total * 100, 1) if total else 0
        tv_pct = round(n_tv / total * 100, 1) if total else 0
        yr_min = int(filtered['release_year'].min()) if total else 0
        yr_max = int(filtered['release_year'].max()) if total else 0
        n_countries = filtered['country'].str.split(', ').explode().str.strip().loc[lambda s: s != ''].nunique()
        n_genres = filtered['listed_in'].str.split(', ').explode().str.strip().nunique()

        pdf.set_font('Helvetica', '', 11)
        for line in [
            f'Total Titles: {total:,}',
            f'Movies: {n_movies:,} ({movie_pct}%)',
            f'TV Shows: {n_tv:,} ({tv_pct}%)',
            f'Release Year Range: {yr_min} - {yr_max}',
            f'Countries Represented: {n_countries}',
            f'Genres Represented: {n_genres}',
        ]:
            pdf.cell(0, 8, line, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(8)

        # ── Type Breakdown ──
        _pdf_section_title(pdf, 'Type Distribution', safe_text)
        _pdf_table(pdf, ['Type', 'Count', '% of Total'],
                   [['Movie', f'{n_movies:,}', f'{movie_pct}%'],
                    ['TV Show', f'{n_tv:,}', f'{tv_pct}%']],
                   [40, 30, 30], safe_text)
        pdf.ln(8)

        # ── Rating Distribution ──
        _pdf_section_title(pdf, 'Rating Distribution', safe_text)
        ratings = filtered['rating'].loc[filtered['rating'] != ''].value_counts().head(10)
        _pdf_table(pdf, ['Rating', 'Count', '% of Filtered'],
                   [[r, f'{c:,}', f'{c / total * 100:.1f}%'] for r, c in ratings.items()],
                   [40, 30, 30], safe_text)

        # ── Page 3: Genres + Countries ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Top 10 Genres', safe_text)
        genres = (
            filtered['listed_in'].str.split(', ').explode().str.strip()
            .value_counts().head(10)
        )
        _pdf_table(pdf, ['Genre', 'Count', '% of Filtered'],
                   [[safe_text(g), f'{n:,}', f'{n / total * 100:.1f}%'] for g, n in genres.items()],
                   [60, 30, 30], safe_text)
        pdf.ln(8)

        _pdf_section_title(pdf, 'Top 10 Countries', safe_text)
        countries = (
            filtered['country'].str.split(', ').explode().str.strip()
            .loc[lambda s: s != ''].value_counts().head(10)
        )
        _pdf_table(pdf, ['Country', 'Count', '% of Filtered'],
                   [[safe_text(c), f'{n:,}', f'{n / total * 100:.1f}%'] for c, n in countries.items()],
                   [50, 30, 30], safe_text)

        # ── Page 4: Year Breakdown ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Titles by Release Year', safe_text)
        yearly = filtered['release_year'].value_counts().sort_index()
        recent = {y: c for y, c in yearly.items() if y >= max(yr_min, yr_max - 14)}
        prev = None
        year_rows = []
        for y, c in recent.items():
            m = int((filtered[(filtered['release_year'] == y) & (filtered['type'] == 'Movie')].shape[0]))
            t = int((filtered[(filtered['release_year'] == y) & (filtered['type'] == 'TV Show')].shape[0]))
            change = ''
            if prev is not None and prev > 0:
                change = f'{(c - prev) / prev * 100:+.1f}%'
            year_rows.append([str(int(y)), f'{c:,}', f'{m:,}', f'{t:,}', change])
            prev = c
        _pdf_table(pdf, ['Year', 'Total', 'Movies', 'TV Shows', 'YoY Change'],
                   year_rows, [22, 22, 22, 22, 25], safe_text)
        pdf.ln(8)

        # ── Top Directors ──
        directors = filtered['director'].loc[filtered['director'] != ''].value_counts().head(10)
        if len(directors) > 0:
            _pdf_section_title(pdf, 'Top 10 Directors', safe_text)
            _pdf_table(pdf, ['Director', 'Titles'],
                       [[safe_text(d), f'{n:,}'] for d, n in directors.items()],
                       [60, 30], safe_text)

        # ── Page 5: Duration Analysis (movies) ──
        f_movies = filtered[filtered['type'] == 'Movie'].copy()
        f_movies['dur_min'] = f_movies['duration'].str.extract(r'(\d+)').astype(float)
        if len(f_movies) > 0 and f_movies['dur_min'].notna().any():
            pdf.add_page()
            _pdf_section_title(pdf, 'Movie Duration Analysis', safe_text)
            pdf.set_font('Helvetica', '', 11)
            avg = f_movies['dur_min'].mean()
            median = f_movies['dur_min'].median()
            shortest = f_movies.loc[f_movies['dur_min'].idxmin()]
            longest = f_movies.loc[f_movies['dur_min'].idxmax()]
            for line in [
                f'Average Duration: {avg:.0f} min',
                f'Median Duration: {median:.0f} min',
                f'Shortest: {safe_text(str(shortest["title"]))} ({int(shortest["dur_min"])} min)',
                f'Longest: {safe_text(str(longest["title"]))} ({int(longest["dur_min"])} min)',
            ]:
                pdf.cell(0, 8, line, new_x='LMARGIN', new_y='NEXT')
            pdf.ln(6)

            # Duration by year
            _pdf_section_title(pdf, 'Avg Movie Duration by Year', safe_text)
            avg_by_year = f_movies.groupby('release_year')['dur_min'].mean()
            dur_rows = [[str(int(y)), f'{d:.1f} min']
                        for y, d in avg_by_year.items() if y >= max(yr_min, yr_max - 10) and pd.notna(d)]
            _pdf_table(pdf, ['Year', 'Avg Duration'], dur_rows, [30, 40], safe_text)

        # Output
        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)
        filename = f'netflix_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Visual PDF Export (charts as images) ─────────────────────────────────────

@app.route('/api/export/visual-pdf', methods=['POST'])
@login_required
def api_export_visual_pdf():
    """Accepts chart images from the browser and composes them into a PDF."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        title = data.get('title', 'Netflix Data Explorer Report')
        charts = data.get('charts', [])  # [{name, image}] image = base64 data URL
        summary = data.get('summary', '')

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title page
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 28)
        pdf.ln(50)
        pdf.cell(0, 15, 'Netflix Data Explorer', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 16)
        safe_title = title.encode('latin-1', errors='replace').decode('latin-1')
        pdf.cell(0, 10, safe_title, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(10)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
        if summary:
            safe_summary = summary.encode('latin-1', errors='replace').decode('latin-1')
            pdf.cell(0, 8, safe_summary, align='C', new_x='LMARGIN', new_y='NEXT')

        # Chart pages - 2 charts per landscape page
        for i in range(0, len(charts), 2):
            pdf.add_page('L')

            for j in range(2):
                idx = i + j
                if idx >= len(charts):
                    break

                chart = charts[idx]
                name = chart.get('name', f'Chart {idx + 1}')
                image_data = chart.get('image', '')

                # Decode base64 image
                if ',' in image_data:
                    image_data = image_data.split(',', 1)[1]

                img_bytes = base64.b64decode(image_data)
                img_buf = io.BytesIO(img_bytes)

                # Position: left half or right half
                x = 10 if j == 0 else 150
                y = 15

                # Chart title
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_text_color(0, 0, 0)
                safe_name = name.encode('latin-1', errors='replace').decode('latin-1')
                pdf.set_xy(x, y)
                pdf.cell(130, 8, safe_name)

                # Chart image
                pdf.image(img_buf, x=x, y=y + 10, w=128, h=80)

        # Output
        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)

        filename = f'netflix_visual_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Stats PDF Export ─────────────────────────────────────────────────────────

def _pdf_section_title(pdf, text, safe_text_fn):
    """Render a red section header in the PDF."""
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(229, 9, 20)
    pdf.cell(0, 10, safe_text_fn(text), new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _pdf_table(pdf, headers, rows, col_widths, safe_text_fn):
    """Render a table with red header row."""
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(229, 9, 20)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    for row_data in rows:
        for i, val in enumerate(row_data):
            pdf.cell(col_widths[i], 7, safe_text_fn(str(val)), border=1)
        pdf.ln()


@app.route('/api/export/stats-pdf')
@login_required
@require_api_key
def api_export_stats_pdf():
    try:
        def safe_text(text):
            if not text:
                return ''
            replacements = {
                '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
                '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00e9': 'e',
                '\u00e1': 'a', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
                '\u00f1': 'n', '\u00fc': 'u', '\u00e8': 'e', '\u00e0': 'a',
            }
            for k, v in replacements.items():
                text = text.replace(k, v)
            return text.encode('latin-1', errors='replace').decode('latin-1')

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ── Title Page ──
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 28)
        pdf.ln(50)
        pdf.cell(0, 15, 'Netflix Data Explorer', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 16)
        pdf.cell(0, 10, 'Statistics Report', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(10)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.cell(0, 8, f'Dataset: {len(df):,} titles ({int((df["type"] == "Movie").sum()):,} Movies, {int((df["type"] == "TV Show").sum()):,} TV Shows)', align='C', new_x='LMARGIN', new_y='NEXT')

        # ── Overview ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Overview', safe_text)
        pdf.set_font('Helvetica', '', 11)
        overview = [
            f'Total Titles: {len(df):,}',
            f'Movies: {int((df["type"] == "Movie").sum()):,} (69.6%)',
            f'TV Shows: {int((df["type"] == "TV Show").sum()):,} (30.4%)',
            f'Year Range: {int(df["release_year"].min())} - {int(df["release_year"].max())}',
            f'Unique Countries: {len(FILTER_OPTIONS["countries"])}',
            f'Unique Genres: {len(FILTER_OPTIONS["genres"])}',
        ]
        for line in overview:
            pdf.cell(0, 8, line, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(8)

        # ── Rating Distribution ──
        _pdf_section_title(pdf, 'Rating Distribution', safe_text)
        ratings = df['rating'].loc[df['rating'] != ''].value_counts().head(15)
        _pdf_table(pdf,
            ['Rating', 'Count', '% of Total'],
            [[r, f'{c:,}', f'{c / len(df) * 100:.1f}%'] for r, c in ratings.items()],
            [40, 30, 30], safe_text)
        pdf.ln(8)

        # ── Top 10 Countries ──
        _pdf_section_title(pdf, 'Top 10 Countries', safe_text)
        countries = (
            df['country'].str.split(', ').explode().str.strip()
            .loc[lambda s: s != ''].value_counts().head(10)
        )
        _pdf_table(pdf,
            ['Country', 'Count', '% of Total'],
            [[c, f'{n:,}', f'{n / len(df) * 100:.1f}%'] for c, n in countries.items()],
            [50, 30, 30], safe_text)

        # ── Top 10 Genres ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Top 10 Genres', safe_text)
        genres = (
            df['listed_in'].str.split(', ').explode().str.strip()
            .value_counts().head(10)
        )
        _pdf_table(pdf,
            ['Genre', 'Count', '% of Total'],
            [[g, f'{n:,}', f'{n / len(df) * 100:.1f}%'] for g, n in genres.items()],
            [60, 30, 30], safe_text)
        pdf.ln(8)

        # ── Titles by Year (last 15 years) ──
        _pdf_section_title(pdf, 'Titles by Release Year (2007-2021)', safe_text)
        yearly = df['release_year'].value_counts().sort_index()
        recent = {y: c for y, c in yearly.items() if y >= 2007}
        _pdf_table(pdf,
            ['Year', 'Total', 'Movies', 'TV Shows'],
            [[str(int(y)),
              f'{c:,}',
              f'{int((df[(df["release_year"] == y) & (df["type"] == "Movie")].shape[0])):,}',
              f'{int((df[(df["release_year"] == y) & (df["type"] == "TV Show")].shape[0])):,}']
             for y, c in recent.items()],
            [25, 25, 30, 30], safe_text)

        # Output
        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=f'netflix_stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Analysis PDF Export ──────────────────────────────────────────────────────

@app.route('/api/export/analysis-pdf')
@login_required
@require_api_key
def api_export_analysis_pdf():
    try:
        def safe_text(text):
            if not text:
                return ''
            replacements = {
                '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
                '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00e9': 'e',
                '\u00e1': 'a', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
                '\u00f1': 'n', '\u00fc': 'u', '\u00e8': 'e', '\u00e0': 'a',
            }
            for k, v in replacements.items():
                text = text.replace(k, v)
            return text.encode('latin-1', errors='replace').decode('latin-1')

        year1 = request.args.get('year1', type=int)
        year2 = request.args.get('year2', type=int)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ── Title Page ──
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 28)
        pdf.ln(50)
        pdf.cell(0, 15, 'Netflix Data Explorer', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 16)
        pdf.cell(0, 10, 'Year-over-Year Analysis Report', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(10)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
        if year1 and year2:
            pdf.cell(0, 8, f'Comparing: {year1} vs {year2}', align='C', new_x='LMARGIN', new_y='NEXT')

        # ── YoY Growth ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Year-over-Year Growth', safe_text)
        yearly = df['release_year'].value_counts().sort_index()
        prev = None
        yoy_rows = []
        for y, c in yearly.items():
            if y >= 2010:
                change = ''
                if prev is not None:
                    pct = (c - prev) / prev * 100 if prev > 0 else 0
                    change = f'{pct:+.1f}%'
                yoy_rows.append([str(int(y)), f'{c:,}', change])
            prev = c
        _pdf_table(pdf, ['Year', 'Titles', 'YoY Change'], yoy_rows, [25, 30, 30], safe_text)
        pdf.ln(8)

        # ── Movies vs TV Shows Share ──
        _pdf_section_title(pdf, 'Movies vs TV Shows Share by Year', safe_text)
        type_by_year = df.groupby(['release_year', 'type']).size().unstack(fill_value=0)
        share_rows = []
        for y in sorted(type_by_year.index):
            if y >= 2010:
                row = type_by_year.loc[y]
                total = row.sum()
                m = int(row.get('Movie', 0))
                t = int(row.get('TV Show', 0))
                share_rows.append([
                    str(int(y)), f'{m:,}', f'{m/total*100:.1f}%',
                    f'{t:,}', f'{t/total*100:.1f}%'
                ])
        _pdf_table(pdf, ['Year', 'Movies', 'Movie %', 'TV Shows', 'TV %'],
                   share_rows, [20, 22, 22, 22, 22], safe_text)

        # ── Avg Movie Duration ──
        pdf.add_page()
        _pdf_section_title(pdf, 'Average Movie Duration Trend', safe_text)
        movies = df[df['type'] == 'Movie'].copy()
        movies['duration_min'] = movies['duration'].str.extract(r'(\d+)').astype(float)
        avg_dur = movies.groupby('release_year')['duration_min'].mean()
        dur_rows = [[str(int(y)), f'{d:.1f} min']
                    for y, d in avg_dur.items() if y >= 2010 and pd.notna(d)]
        _pdf_table(pdf, ['Year', 'Avg Duration'], dur_rows, [30, 40], safe_text)
        pdf.ln(8)

        # ── Top Genres Trend ──
        _pdf_section_title(pdf, 'Top 5 Genres Trend (Last 7 Years)', safe_text)
        top_genres = (
            df['listed_in'].str.split(', ').explode().str.strip()
            .value_counts().head(5).index.tolist()
        )
        max_year = int(df['release_year'].max())
        genre_years = list(range(max_year - 6, max_year + 1))
        genre_rows = []
        for genre in top_genres:
            row = [safe_text(genre)]
            for y in genre_years:
                mask = (df['release_year'] == y) & df['listed_in'].str.contains(genre, case=False, na=False)
                row.append(str(int(mask.sum())))
            genre_rows.append(row)
        genre_widths = [45] + [18] * len(genre_years)
        _pdf_table(pdf, ['Genre'] + [str(y) for y in genre_years],
                   genre_rows, genre_widths, safe_text)

        # ── Year Comparison ──
        if year1 and year2:
            pdf.add_page()
            _pdf_section_title(pdf, f'Comparison: {year1} vs {year2}', safe_text)

            def year_data(yr):
                subset = df[df['release_year'] == yr]
                return {
                    'total': len(subset),
                    'movies': int((subset['type'] == 'Movie').sum()),
                    'tv_shows': int((subset['type'] == 'TV Show').sum()),
                    'top_genres': (
                        subset['listed_in'].str.split(', ').explode().str.strip()
                        .value_counts().head(5).to_dict()
                    ),
                    'top_countries': (
                        subset['country'].str.split(', ').explode().str.strip()
                        .loc[lambda s: s != ''].value_counts().head(5).to_dict()
                    ),
                    'ratings': subset['rating'].value_counts().head(5).to_dict(),
                }

            d1, d2 = year_data(year1), year_data(year2)

            # Summary comparison
            _pdf_table(pdf,
                ['Metric', str(year1), str(year2), 'Change'],
                [
                    ['Total Titles', f'{d1["total"]:,}', f'{d2["total"]:,}',
                     f'{d2["total"] - d1["total"]:+,}'],
                    ['Movies', f'{d1["movies"]:,}', f'{d2["movies"]:,}',
                     f'{d2["movies"] - d1["movies"]:+,}'],
                    ['TV Shows', f'{d1["tv_shows"]:,}', f'{d2["tv_shows"]:,}',
                     f'{d2["tv_shows"] - d1["tv_shows"]:+,}'],
                ],
                [35, 30, 30, 30], safe_text)
            pdf.ln(8)

            # Genre comparison
            _pdf_section_title(pdf, f'Top Genres: {year1} vs {year2}', safe_text)
            all_genres = set(list(d1['top_genres'].keys()) + list(d2['top_genres'].keys()))
            genre_comp = [[safe_text(g), str(d1['top_genres'].get(g, 0)),
                          str(d2['top_genres'].get(g, 0)),
                          f'{d2["top_genres"].get(g, 0) - d1["top_genres"].get(g, 0):+d}']
                         for g in sorted(all_genres, key=lambda g: d2['top_genres'].get(g, 0), reverse=True)]
            _pdf_table(pdf, ['Genre', str(year1), str(year2), 'Change'],
                       genre_comp, [50, 25, 25, 25], safe_text)
            pdf.ln(8)

            # Country comparison
            _pdf_section_title(pdf, f'Top Countries: {year1} vs {year2}', safe_text)
            all_countries = set(list(d1['top_countries'].keys()) + list(d2['top_countries'].keys()))
            country_comp = [[safe_text(c), str(d1['top_countries'].get(c, 0)),
                            str(d2['top_countries'].get(c, 0)),
                            f'{d2["top_countries"].get(c, 0) - d1["top_countries"].get(c, 0):+d}']
                           for c in sorted(all_countries, key=lambda c: d2['top_countries'].get(c, 0), reverse=True)]
            _pdf_table(pdf, ['Country', str(year1), str(year2), 'Change'],
                       country_comp, [45, 25, 25, 25], safe_text)
            pdf.ln(8)

            # Rating comparison
            _pdf_section_title(pdf, f'Rating Distribution: {year1} vs {year2}', safe_text)
            all_ratings = set(list(d1['ratings'].keys()) + list(d2['ratings'].keys()))
            rating_comp = [[r, str(d1['ratings'].get(r, 0)), str(d2['ratings'].get(r, 0)),
                           f'{d2["ratings"].get(r, 0) - d1["ratings"].get(r, 0):+d}']
                          for r in sorted(all_ratings, key=lambda r: d2['ratings'].get(r, 0), reverse=True)]
            _pdf_table(pdf, ['Rating', str(year1), str(year2), 'Change'],
                       rating_comp, [35, 25, 25, 25], safe_text)

        # Output
        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=f'netflix_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"  Loaded {len(df)} titles from CSV")
    print(f"  Filters: {len(FILTER_OPTIONS['genres'])} genres, {len(FILTER_OPTIONS['countries'])} countries")
    print(f"  Login: username={config.APP_USERNAME}")
    app.run(debug=True, port=5001)
