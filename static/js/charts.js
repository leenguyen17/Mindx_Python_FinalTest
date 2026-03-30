/**
 * Netflix Data Explorer — Chart.js Renderers
 * Creates and manages Chart.js instances with destroy-before-create pattern.
 */

const Charts = (() => {
    const instances = {};

    const COLORS = {
        red: '#e50914',
        redDark: '#b20710',
        blue: '#3466e5',
        green: '#2ecc71',
        purple: '#8b5cf6',
        yellow: '#f59e0b',
        orange: '#f97316',
        pink: '#ec4899',
        teal: '#14b8a6',
        cyan: '#06b6d4',
    };

    const PALETTE = [COLORS.red, COLORS.blue, COLORS.green, COLORS.purple, COLORS.yellow,
                     COLORS.orange, COLORS.pink, COLORS.teal, COLORS.cyan, COLORS.redDark];

    const BASE_OPTIONS = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { labels: { color: '#999', font: { family: 'DM Sans', size: 12 } } },
        },
        scales: {
            x: { ticks: { color: '#666', font: { family: 'DM Sans', size: 11 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
            y: { ticks: { color: '#666', font: { family: 'DM Sans', size: 11 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
        },
    };

    function getOrCreate(canvasId, config) {
        if (instances[canvasId]) {
            instances[canvasId].destroy();
        }
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        instances[canvasId] = new Chart(ctx, config);
        return instances[canvasId];
    }

    // ─── Stats Charts ────────────────────────────────────

    function renderTypeDonut(stats) {
        getOrCreate('chartTypeDonut', {
            type: 'doughnut',
            data: {
                labels: ['Movies', 'TV Shows'],
                datasets: [{
                    data: [stats.total_movies, stats.total_tv_shows],
                    backgroundColor: [COLORS.red, COLORS.blue],
                    borderWidth: 0,
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                cutout: '60%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#999', padding: 16, font: { family: 'DM Sans' } } },
                },
            },
        });
    }

    function renderByYear(stats) {
        const data = stats.by_year || {};
        // Last 20 years
        const years = Object.keys(data).map(Number).filter(y => y >= 2000).sort();
        getOrCreate('chartByYear', {
            type: 'bar',
            data: {
                labels: years,
                datasets: [{
                    label: 'Titles',
                    data: years.map(y => data[y] || 0),
                    backgroundColor: years.map((_, i) => {
                        const t = i / years.length;
                        return `rgba(229, 9, 20, ${0.4 + t * 0.6})`;
                    }),
                    borderRadius: 3,
                }],
            },
            options: { ...BASE_OPTIONS, plugins: { legend: { display: false } } },
        });
    }

    function renderByRating(stats) {
        const data = stats.by_rating || {};
        const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, 10);
        getOrCreate('chartByRating', {
            type: 'bar',
            data: {
                labels: sorted.map(e => e[0]),
                datasets: [{
                    label: 'Count',
                    data: sorted.map(e => e[1]),
                    backgroundColor: PALETTE,
                    borderRadius: 3,
                }],
            },
            options: {
                ...BASE_OPTIONS,
                indexAxis: 'y',
                plugins: { legend: { display: false } },
            },
        });
    }

    function renderByCountry(stats) {
        const data = stats.by_country_top10 || {};
        const entries = Object.entries(data);
        getOrCreate('chartByCountry', {
            type: 'bar',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    label: 'Titles',
                    data: entries.map(e => e[1]),
                    backgroundColor: PALETTE,
                    borderRadius: 3,
                }],
            },
            options: { ...BASE_OPTIONS, plugins: { legend: { display: false } } },
        });
    }

    function renderByGenre(stats) {
        const data = stats.by_genre_top10 || {};
        const entries = Object.entries(data);
        getOrCreate('chartByGenre', {
            type: 'bar',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    label: 'Titles',
                    data: entries.map(e => e[1]),
                    backgroundColor: PALETTE,
                    borderRadius: 3,
                }],
            },
            options: {
                ...BASE_OPTIONS,
                indexAxis: 'y',
                plugins: { legend: { display: false } },
            },
        });
    }

    function renderTimeline(stats) {
        const data = stats.added_by_year_month || {};
        const months = Object.keys(data).sort();
        // Sample every 3 months for readability
        const sampled = months.filter((_, i) => i % 3 === 0);
        getOrCreate('chartTimeline', {
            type: 'line',
            data: {
                labels: sampled,
                datasets: [{
                    label: 'Added',
                    data: sampled.map(m => data[m] || 0),
                    borderColor: COLORS.red,
                    backgroundColor: 'rgba(229,9,20,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                }],
            },
            options: {
                ...BASE_OPTIONS,
                plugins: { legend: { display: false } },
                scales: {
                    ...BASE_OPTIONS.scales,
                    x: { ...BASE_OPTIONS.scales.x, ticks: { ...BASE_OPTIONS.scales.x.ticks, maxRotation: 45 } },
                },
            },
        });
    }

    function renderAllStats(stats) {
        renderTypeDonut(stats);
        renderByYear(stats);
        renderByRating(stats);
        renderByCountry(stats);
        renderByGenre(stats);
        renderTimeline(stats);
    }

    // ─── Analysis Charts ─────────────────────────────────

    function renderTypeShare(analysis) {
        const data = analysis.type_share_by_year || {};
        const years = Object.keys(data).map(Number).filter(y => y >= 2010).sort();
        getOrCreate('chartTypeShare', {
            type: 'line',
            data: {
                labels: years,
                datasets: [
                    {
                        label: 'Movies',
                        data: years.map(y => data[y]?.Movie || 0),
                        borderColor: COLORS.red,
                        backgroundColor: 'rgba(229,9,20,0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'TV Shows',
                        data: years.map(y => data[y]?.['TV Show'] || 0),
                        borderColor: COLORS.blue,
                        backgroundColor: 'rgba(52,102,229,0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                ],
            },
            options: BASE_OPTIONS,
        });
    }

    function renderYoYGrowth(analysis) {
        const data = analysis.yoy_growth || {};
        const years = Object.keys(data).map(Number).filter(y => y >= 2010).sort();
        const changes = years.map(y => data[y]?.change_pct ?? 0);
        getOrCreate('chartYoYGrowth', {
            type: 'bar',
            data: {
                labels: years,
                datasets: [{
                    label: 'YoY Change %',
                    data: changes,
                    backgroundColor: changes.map(c => c >= 0 ? 'rgba(46,204,113,0.7)' : 'rgba(255,107,107,0.7)'),
                    borderRadius: 3,
                }],
            },
            options: { ...BASE_OPTIONS, plugins: { legend: { display: false } } },
        });
    }

    function renderGenreTrend(analysis) {
        const data = analysis.genre_trends || {};
        const genres = Object.keys(data).slice(0, 5);
        const allYears = new Set();
        genres.forEach(g => Object.keys(data[g]).forEach(y => allYears.add(Number(y))));
        const years = [...allYears].sort();

        getOrCreate('chartGenreTrend', {
            type: 'line',
            data: {
                labels: years,
                datasets: genres.map((genre, i) => ({
                    label: genre,
                    data: years.map(y => data[genre]?.[y] || 0),
                    borderColor: PALETTE[i],
                    tension: 0.3,
                    pointRadius: 3,
                })),
            },
            options: BASE_OPTIONS,
        });
    }

    function renderDuration(analysis) {
        const data = analysis.avg_movie_duration || {};
        const years = Object.keys(data).map(Number).filter(y => y >= 2000).sort();
        getOrCreate('chartDuration', {
            type: 'line',
            data: {
                labels: years,
                datasets: [{
                    label: 'Avg Duration (min)',
                    data: years.map(y => data[y] || 0),
                    borderColor: COLORS.purple,
                    backgroundColor: 'rgba(139,92,246,0.1)',
                    fill: true,
                    tension: 0.3,
                }],
            },
            options: { ...BASE_OPTIONS, plugins: { legend: { display: false } } },
        });
    }

    function renderCountryTrend(analysis) {
        const data = analysis.country_trends || {};
        const countries = Object.keys(data);
        const allYears = new Set();
        countries.forEach(c => Object.keys(data[c]).forEach(y => allYears.add(Number(y))));
        const years = [...allYears].sort();

        getOrCreate('chartCountryTrend', {
            type: 'line',
            data: {
                labels: years,
                datasets: countries.map((country, i) => ({
                    label: country,
                    data: years.map(y => data[country]?.[y] || 0),
                    borderColor: PALETTE[i],
                    tension: 0.3,
                    pointRadius: 3,
                })),
            },
            options: BASE_OPTIONS,
        });
    }

    function renderRatingShift(analysis) {
        const data = analysis.rating_by_year || {};
        const years = Object.keys(data).map(Number).sort();
        const topRatings = ['TV-MA', 'TV-14', 'TV-PG', 'R', 'PG-13'];

        getOrCreate('chartRatingShift', {
            type: 'bar',
            data: {
                labels: years,
                datasets: topRatings.map((rating, i) => ({
                    label: rating,
                    data: years.map(y => data[y]?.[rating] || 0),
                    backgroundColor: PALETTE[i] + 'cc',
                    borderRadius: 2,
                })),
            },
            options: {
                ...BASE_OPTIONS,
                scales: {
                    ...BASE_OPTIONS.scales,
                    x: { ...BASE_OPTIONS.scales.x, stacked: true },
                    y: { ...BASE_OPTIONS.scales.y, stacked: true },
                },
            },
        });
    }

    function renderAllAnalysis(analysis) {
        renderTypeShare(analysis);
        renderYoYGrowth(analysis);
        renderGenreTrend(analysis);
        renderDuration(analysis);
        renderCountryTrend(analysis);
        renderRatingShift(analysis);
    }

    return { renderAllStats, renderAllAnalysis };
})();
