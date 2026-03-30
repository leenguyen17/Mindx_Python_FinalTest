/**
 * Netflix Data Explorer — Main Application
 * State management, event binding, and orchestration.
 */

(() => {
    // ─── State ───────────────────────────────────────────

    const state = {
        currentView: 'browse',
        filters: { type: '', rating: '', genre: '', country: '', year_min: '', year_max: '', search: '' },
        sort: { sort_by: 'date_added', sort_order: 'desc' },
        page: 1,
        perPage: 20,
        statsLoaded: false,
        analysisLoaded: false,
    };

    // ─── DOM References ──────────────────────────────────

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const els = {
        titleGrid: $('#titleGrid'),
        pagination: $('#pagination'),
        resultsCount: $('#resultsCount'),
        searchInput: $('#searchInput'),
        filterType: $('#filterType'),
        filterRating: $('#filterRating'),
        filterGenre: $('#filterGenre'),
        filterCountry: $('#filterCountry'),
        filterYearMin: $('#filterYearMin'),
        filterYearMax: $('#filterYearMax'),
        exportPdfBtn: $('#exportPdfBtn'),
        clearFiltersBtn: $('#clearFiltersBtn'),
        modal: $('#detailModal'),
        modalContent: $('#modalContent'),
        modalClose: $('#modalClose'),
        statsSummary: $('#statsSummary'),
        comparisonCards: $('#comparisonCards'),
        compareYear1: $('#compareYear1'),
        compareYear2: $('#compareYear2'),
        compareBtn: $('#compareBtn'),
        exportStatsPdfBtn: $('#exportStatsPdfBtn'),
        exportAnalysisPdfBtn: $('#exportAnalysisPdfBtn'),
    };

    // ─── View Switching ──────────────────────────────────

    function switchView(view) {
        state.currentView = view;
        $$('.view').forEach(v => v.classList.remove('active'));
        $(`#${view}View`).classList.add('active');
        $$('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));

        if (view === 'stats' && !state.statsLoaded) loadStats();
        if (view === 'analysis' && !state.analysisLoaded) loadAnalysis();
    }

    // ─── Browse ──────────────────────────────────────────

    let fetchController = null;

    async function loadTitles() {
        if (fetchController) fetchController.abort();
        fetchController = new AbortController();

        els.titleGrid.innerHTML = Components.renderSkeletons(8);
        els.pagination.innerHTML = '';

        try {
            const params = {
                ...state.filters,
                ...state.sort,
                page: state.page,
                per_page: state.perPage,
            };

            const data = await API.fetchTitles(params);
            els.titleGrid.innerHTML = Components.renderTitleGrid(data.titles);
            els.pagination.innerHTML = Components.renderPagination(data.pagination);
            els.resultsCount.textContent = `${data.pagination.total.toLocaleString()} titles`;

            // Bind card clicks
            els.titleGrid.querySelectorAll('.title-card').forEach(card => {
                card.addEventListener('click', () => openModal(card.dataset.id));
            });

            // Bind empty state clear button
            const clearEmpty = $('#clearFiltersFromEmpty');
            if (clearEmpty) clearEmpty.addEventListener('click', clearFilters);

            // Bind retry
            const retryBtn = $('#retryBtn');
            if (retryBtn) retryBtn.addEventListener('click', loadTitles);

        } catch (err) {
            if (err.name === 'AbortError') return;
            els.titleGrid.innerHTML = Components.renderErrorState(err.message);
            const retryBtn = $('#retryBtn');
            if (retryBtn) retryBtn.addEventListener('click', loadTitles);
        }
    }

    // ─── Modal ───────────────────────────────────────────

    async function openModal(showId) {
        els.modal.hidden = false;
        document.body.style.overflow = 'hidden';
        els.modalContent.innerHTML = '<div style="text-align:center;padding:40px;color:#666">Loading...</div>';

        try {
            const title = await API.fetchTitle(showId);
            els.modalContent.innerHTML = Components.renderModal(title);
        } catch (err) {
            els.modalContent.innerHTML = `<p style="color:#ff6b6b;text-align:center;padding:40px">${err.message}</p>`;
        }
    }

    function closeModal() {
        els.modal.hidden = true;
        document.body.style.overflow = '';
    }

    // ─── Stats ───────────────────────────────────────────

    async function loadStats() {
        try {
            const stats = await API.fetchStats();
            els.statsSummary.innerHTML = Components.renderStatsSummary(stats);
            Charts.renderAllStats(stats);
            state.statsLoaded = true;
        } catch (err) {
            els.statsSummary.innerHTML = Components.renderErrorState(err.message);
        }
    }

    // ─── Analysis ────────────────────────────────────────

    async function loadAnalysis() {
        try {
            const analysis = await API.fetchAnalysis();
            Charts.renderAllAnalysis(analysis);
            state.analysisLoaded = true;
        } catch (err) {
            console.error('Analysis load error:', err);
        }
    }

    async function loadComparison() {
        const y1 = els.compareYear1.value;
        const y2 = els.compareYear2.value;
        if (!y1 || !y2) return;

        try {
            const analysis = await API.fetchAnalysis({ year1: y1, year2: y2 });
            if (analysis.comparison) {
                els.comparisonCards.innerHTML = Components.renderComparisonCards(analysis.comparison);
            }
        } catch (err) {
            els.comparisonCards.innerHTML = `<p style="color:#ff6b6b">${err.message}</p>`;
        }
    }

    // ─── Filters ─────────────────────────────────────────

    function readFilters() {
        state.filters.type = els.filterType.value;
        state.filters.rating = els.filterRating.value;
        state.filters.genre = els.filterGenre.value;
        state.filters.country = els.filterCountry.value;
        state.filters.year_min = els.filterYearMin.value;
        state.filters.year_max = els.filterYearMax.value;
        state.filters.search = els.searchInput.value.trim();
    }

    function onFilterChange() {
        readFilters();
        state.page = 1;
        loadTitles();
    }

    function clearFilters() {
        els.filterType.value = '';
        els.filterRating.value = '';
        els.filterGenre.value = '';
        els.filterCountry.value = '';
        els.filterYearMin.value = '';
        els.filterYearMax.value = '';
        els.searchInput.value = '';
        onFilterChange();
    }

    // ─── Debounced Search ────────────────────────────────

    let searchTimeout = null;
    function onSearchInput() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            readFilters();
            state.page = 1;
            loadTitles();
        }, 300);
    }

    // ─── Pagination ──────────────────────────────────────

    function onPaginationClick(e) {
        const btn = e.target.closest('.page-btn');
        if (!btn || btn.classList.contains('disabled') || btn.classList.contains('active')) return;
        state.page = parseInt(btn.dataset.page, 10);
        loadTitles();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // ─── Export PDF ──────────────────────────────────────

    function onExportPdf() {
        readFilters();
        const url = API.getExportPdfUrl({ ...state.filters, ...state.sort });
        window.open(url, '_blank');
    }

    // ─── Visual PDF Export (captures charts as images) ───

    async function exportVisualPdf(viewType) {
        const btn = viewType === 'stats' ? els.exportStatsPdfBtn : els.exportAnalysisPdfBtn;
        const origText = btn.innerHTML;
        btn.innerHTML = 'Generating...';
        btn.disabled = true;

        try {
            // Determine which canvases to capture
            const canvasIds = viewType === 'stats'
                ? ['chartTypeDonut', 'chartByYear', 'chartByRating', 'chartByCountry', 'chartByGenre', 'chartTimeline']
                : ['chartTypeShare', 'chartYoYGrowth', 'chartGenreTrend', 'chartDuration', 'chartCountryTrend', 'chartRatingShift'];

            const chartNames = viewType === 'stats'
                ? ['Type Distribution', 'Titles by Release Year', 'Rating Distribution', 'Top 10 Countries', 'Top 10 Genres', 'Titles Added Over Time']
                : ['Movies vs TV Shows Trend', 'YoY Growth Rate', 'Genre Evolution (Top 5)', 'Avg Movie Duration Trend', 'Country Production Trend', 'Rating Shift Over Years'];

            const charts = [];
            for (let i = 0; i < canvasIds.length; i++) {
                const canvas = document.getElementById(canvasIds[i]);
                if (canvas) {
                    // Create a white-background version for PDF readability
                    const tmpCanvas = document.createElement('canvas');
                    tmpCanvas.width = canvas.width;
                    tmpCanvas.height = canvas.height;
                    const ctx = tmpCanvas.getContext('2d');
                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(0, 0, tmpCanvas.width, tmpCanvas.height);
                    ctx.drawImage(canvas, 0, 0);

                    charts.push({
                        name: chartNames[i],
                        image: tmpCanvas.toDataURL('image/png'),
                    });
                }
            }

            const title = viewType === 'stats' ? 'Statistics Report' : 'Year-over-Year Analysis Report';
            const summary = viewType === 'stats'
                ? `Dataset: ${$('#statsSummary')?.querySelector('.stat-value')?.textContent || ''} titles`
                : `Comparison: ${els.compareYear1.value || '?'} vs ${els.compareYear2.value || '?'}`;

            const res = await fetch('/api/export/visual-pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': window.__API_KEY__,
                },
                body: JSON.stringify({ title, charts, summary }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.error || 'Export failed');
            }

            // Download the PDF
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `netflix_${viewType}_${new Date().toISOString().slice(0, 10)}.pdf`;
            a.click();
            URL.revokeObjectURL(url);

        } catch (err) {
            alert('PDF export failed: ' + err.message);
        } finally {
            btn.innerHTML = origText;
            btn.disabled = false;
        }
    }

    // ─── Init ────────────────────────────────────────────

    async function init() {
        // Load filter options
        try {
            const filters = await API.fetchFilters();
            Components.populateSelect(els.filterType, filters.types, 'All Types');
            Components.populateSelect(els.filterRating, filters.ratings, 'All Ratings');
            Components.populateSelect(els.filterGenre, filters.genres, 'All Genres');
            Components.populateSelect(els.filterCountry, filters.countries, 'All Countries');

            // Year range placeholders
            els.filterYearMin.placeholder = filters.year_min;
            els.filterYearMax.placeholder = filters.year_max;

            // Populate comparison year selects
            const years = [];
            for (let y = filters.year_max; y >= Math.max(filters.year_min, 2000); y--) years.push(y.toString());
            Components.populateSelect(els.compareYear1, years, 'Year 1');
            Components.populateSelect(els.compareYear2, years, 'Year 2');
            // Default comparison
            els.compareYear1.value = '2019';
            els.compareYear2.value = '2021';

        } catch (err) {
            console.error('Failed to load filters:', err);
        }

        // Event listeners
        $$('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => switchView(tab.dataset.view));
        });

        els.filterType.addEventListener('change', onFilterChange);
        els.filterRating.addEventListener('change', onFilterChange);
        els.filterGenre.addEventListener('change', onFilterChange);
        els.filterCountry.addEventListener('change', onFilterChange);
        els.filterYearMin.addEventListener('change', onFilterChange);
        els.filterYearMax.addEventListener('change', onFilterChange);
        els.searchInput.addEventListener('input', onSearchInput);
        els.clearFiltersBtn.addEventListener('click', clearFilters);
        els.exportPdfBtn.addEventListener('click', onExportPdf);
        els.pagination.addEventListener('click', onPaginationClick);
        els.compareBtn.addEventListener('click', loadComparison);
        els.exportStatsPdfBtn.addEventListener('click', () => exportVisualPdf('stats'));
        els.exportAnalysisPdfBtn.addEventListener('click', () => exportVisualPdf('analysis'));

        // Modal
        els.modalClose.addEventListener('click', closeModal);
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !els.modal.hidden) closeModal();
        });

        // Initial load
        loadTitles();
    }

    // ─── Start ───────────────────────────────────────────

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
