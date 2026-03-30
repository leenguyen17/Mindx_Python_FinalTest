"""Netflix Data Explorer - Flask Backend API"""

import io
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
    """Convert dataframe to list of dicts with NaN replaced by None."""
    cols = ['show_id', 'type', 'title', 'director', 'cast', 'country',
            'date_added', 'release_year', 'rating', 'duration', 'listed_in', 'description']
    result = dataframe[cols].copy()
    result = result.where(pd.notnull(result), None)
    # Replace empty strings back to None for cleaner JSON
    result = result.replace('', None)
    return result.to_dict(orient='records')


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

        # Sort
        sort_by = request.args.get('sort_by', 'date_added')
        sort_order = request.args.get('sort_order', 'desc')
        valid_sorts = {'title': 'title', 'release_year': 'release_year', 'date_added': 'date_parsed'}
        sort_col = valid_sorts.get(sort_by, 'date_parsed')
        filtered = filtered.sort_values(sort_col, ascending=(sort_order == 'asc'), na_position='last')

        # Limit to 500
        total = len(filtered)
        export_df = filtered.head(500)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title page
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 28)
        pdf.ln(60)
        pdf.cell(0, 15, 'Netflix Data Explorer', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 14)
        pdf.cell(0, 10, 'Data Export Report', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(10)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.cell(0, 8, f'Total results: {total} | Exported: {len(export_df)}', align='C', new_x='LMARGIN', new_y='NEXT')

        # Filter summary
        filters_applied = []
        for param in ['type', 'rating', 'genre', 'country', 'year_min', 'year_max', 'search']:
            val = request.args.get(param, '').strip()
            if val:
                filters_applied.append(f'{param}: {val}')
        if filters_applied:
            pdf.ln(5)
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 8, f'Filters: {" | ".join(filters_applied)}', align='C', new_x='LMARGIN', new_y='NEXT')

        # Data table
        pdf.add_page('L')  # Landscape for table
        pdf.set_font('Helvetica', 'B', 9)

        col_widths = [50, 18, 14, 30, 22, 40]
        headers = ['Title', 'Type', 'Year', 'Rating', 'Duration', 'Country']

        # Header row
        pdf.set_fill_color(229, 9, 20)  # Netflix red
        pdf.set_text_color(255, 255, 255)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, border=1, fill=True)
        pdf.ln()

        # Data rows
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(0, 0, 0)
        for _, row in export_df.iterrows():
            title = str(row['title'])[:30]
            type_val = str(row['type'])
            year = str(int(row['release_year']))
            rating = str(row['rating'])[:15] if row['rating'] else ''
            duration = str(row['duration'])[:12] if row['duration'] else ''
            country = str(row['country'])[:25] if row['country'] else ''

            pdf.cell(col_widths[0], 7, title, border=1)
            pdf.cell(col_widths[1], 7, type_val, border=1)
            pdf.cell(col_widths[2], 7, year, border=1)
            pdf.cell(col_widths[3], 7, rating, border=1)
            pdf.cell(col_widths[4], 7, duration, border=1)
            pdf.cell(col_widths[5], 7, country, border=1)
            pdf.ln()

        # Output
        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)

        filename = f'netflix_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"  Loaded {len(df)} titles from CSV")
    print(f"  Filters: {len(FILTER_OPTIONS['genres'])} genres, {len(FILTER_OPTIONS['countries'])} countries")
    print(f"  Login: username={config.APP_USERNAME}")
    app.run(debug=True, port=5001)
