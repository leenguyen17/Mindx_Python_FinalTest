/**
 * Netflix Data Explorer — UI Components
 * Pure render functions that return HTML strings.
 */

const Components = (() => {

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function truncate(str, len = 100) {
        if (!str || str.length <= len) return str || '';
        return str.slice(0, len) + '...';
    }

    function renderTitleCard(title) {
        const type = title.type || 'Movie';
        const badgeClass = type === 'Movie' ? 'badge-movie' : 'badge-tvshow';
        const genres = (title.listed_in || '').split(', ').slice(0, 2);
        const meta = [title.release_year, title.rating, title.duration].filter(Boolean).join('  \u2022  ');

        return `
            <article class="title-card" data-id="${escapeHtml(title.show_id)}" data-type="${escapeHtml(type)}">
                <span class="card-badge ${badgeClass}">${escapeHtml(type)}</span>
                <h3 class="card-title">${escapeHtml(title.title)}</h3>
                <p class="card-meta">${escapeHtml(meta)}</p>
                <div class="card-genres">
                    ${genres.map(g => `<span class="genre-tag">${escapeHtml(g.trim())}</span>`).join('')}
                </div>
                <p class="card-desc">${escapeHtml(truncate(title.description, 120))}</p>
            </article>
        `;
    }

    function renderTitleGrid(titles) {
        if (!titles || titles.length === 0) return renderEmptyState();
        return titles.map(renderTitleCard).join('');
    }

    function renderPagination(pag) {
        if (!pag || pag.total_pages <= 1) return '';

        const { page, total_pages } = pag;
        const pages = [];

        // Always show first, last, and pages around current
        const range = 2;
        const start = Math.max(2, page - range);
        const end = Math.min(total_pages - 1, page + range);

        pages.push(1);
        if (start > 2) pages.push('...');
        for (let i = start; i <= end; i++) pages.push(i);
        if (end < total_pages - 1) pages.push('...');
        if (total_pages > 1) pages.push(total_pages);

        const prevDisabled = page <= 1 ? 'disabled' : '';
        const nextDisabled = page >= total_pages ? 'disabled' : '';

        let html = `<button class="page-btn ${prevDisabled}" data-page="${page - 1}">&lsaquo;</button>`;

        for (const p of pages) {
            if (p === '...') {
                html += `<span class="page-ellipsis">...</span>`;
            } else {
                const active = p === page ? 'active' : '';
                html += `<button class="page-btn ${active}" data-page="${p}">${p}</button>`;
            }
        }

        html += `<button class="page-btn ${nextDisabled}" data-page="${page + 1}">&rsaquo;</button>`;
        return html;
    }

    function renderSkeletons(count = 8) {
        let html = '';
        for (let i = 0; i < count; i++) {
            html += `
                <div class="skeleton-card">
                    <div class="skeleton-line w-40 h-8"></div>
                    <div class="skeleton-line w-80 h-20"></div>
                    <div class="skeleton-line w-60"></div>
                    <div class="skeleton-line w-40 h-8"></div>
                    <div class="skeleton-line w-100 h-8"></div>
                    <div class="skeleton-line w-80 h-8"></div>
                </div>
            `;
        }
        return html;
    }

    function renderErrorState(message, onRetry) {
        return `
            <div class="state-container error-container">
                <div class="state-icon">!</div>
                <h3 class="state-title">Something went wrong</h3>
                <p class="state-message">${escapeHtml(message)}</p>
                <button class="state-btn state-btn-primary" id="retryBtn">Try Again</button>
            </div>
        `;
    }

    function renderEmptyState() {
        return `
            <div class="state-container">
                <div class="state-icon" style="opacity:0.3">&#9881;</div>
                <h3 class="state-title">No titles found</h3>
                <p class="state-message">Try adjusting your filters or search terms</p>
                <button class="state-btn state-btn-outline" id="clearFiltersFromEmpty">Clear Filters</button>
            </div>
        `;
    }

    function renderModal(title) {
        const type = title.type || 'Movie';
        const badgeClass = type === 'Movie' ? 'badge-movie' : 'badge-tvshow';
        const meta = [title.release_year, title.rating, title.duration, title.country]
            .filter(Boolean).join('  \u2022  ');
        const genres = (title.listed_in || '').split(', ').filter(Boolean);
        const cast = (title.cast || '').split(', ').filter(Boolean);

        return `
            <span class="modal-badge ${badgeClass}">${escapeHtml(type)}</span>
            <h2 class="modal-title">${escapeHtml(title.title)}</h2>
            <p class="modal-meta">${escapeHtml(meta)}</p>

            ${title.director ? `
            <div class="modal-section">
                <p class="modal-label">Director</p>
                <p class="modal-director">${escapeHtml(title.director)}</p>
            </div>` : ''}

            ${genres.length ? `
            <div class="modal-section">
                <p class="modal-label">Genres</p>
                <div class="modal-genres">
                    ${genres.map(g => `<span class="modal-genre-pill">${escapeHtml(g.trim())}</span>`).join('')}
                </div>
            </div>` : ''}

            ${cast.length ? `
            <div class="modal-section">
                <p class="modal-label">Cast</p>
                <div class="modal-cast-list">
                    ${cast.slice(0, 12).map(c => `<span class="modal-cast-chip">${escapeHtml(c.trim())}</span>`).join('')}
                    ${cast.length > 12 ? `<span class="modal-cast-chip">+${cast.length - 12} more</span>` : ''}
                </div>
            </div>` : ''}

            ${title.date_added ? `
            <div class="modal-section">
                <p class="modal-label">Added to Netflix</p>
                <p>${escapeHtml(title.date_added)}</p>
            </div>` : ''}

            <div class="modal-section">
                <p class="modal-label">Description</p>
                <p class="modal-desc">${escapeHtml(title.description)}</p>
            </div>

            <p class="modal-id">ID: ${escapeHtml(title.show_id)}</p>
        `;
    }

    function renderStatsSummary(stats) {
        const items = [
            { label: 'Total Titles', value: stats.total_titles?.toLocaleString(), color: 'red' },
            { label: 'Movies', value: stats.total_movies?.toLocaleString(), color: 'red' },
            { label: 'TV Shows', value: stats.total_tv_shows?.toLocaleString(), color: 'blue' },
            { label: 'Countries', value: Object.keys(stats.by_country_top10 || {}).length + '+', color: 'green' },
            { label: 'Genres', value: Object.keys(stats.by_genre_top10 || {}).length + '+', color: 'purple' },
        ];

        return items.map(item => `
            <div class="stat-card ${item.color}">
                <div class="stat-value">${item.value}</div>
                <div class="stat-label">${item.label}</div>
            </div>
        `).join('');
    }

    function renderComparisonCards(comparison) {
        if (!comparison) return '';

        const { year1, year2, delta } = comparison;
        const metrics = [
            { label: 'Total Titles', v1: year1.total, v2: year2.total, d: delta.total },
            { label: 'Movies', v1: year1.movies, v2: year2.movies, d: delta.movies },
            { label: 'TV Shows', v1: year1.tv_shows, v2: year2.tv_shows, d: delta.tv_shows },
        ];

        return metrics.map(m => {
            const deltaClass = m.d >= 0 ? 'delta-up' : 'delta-down';
            const arrow = m.d >= 0 ? '\u2191' : '\u2193';
            return `
                <div class="comparison-card">
                    <div class="comp-label">${m.label}</div>
                    <div class="comp-values">
                        <span class="comp-value">${m.v1}</span>
                        <span style="color:var(--text-muted)">\u2192</span>
                        <span class="comp-value">${m.v2}</span>
                        <span class="comp-delta ${deltaClass}">${arrow} ${Math.abs(m.d)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    function populateSelect(selectEl, options, placeholder) {
        selectEl.innerHTML = `<option value="">${placeholder}</option>`;
        options.forEach(opt => {
            const el = document.createElement('option');
            el.value = opt;
            el.textContent = opt;
            selectEl.appendChild(el);
        });
    }

    return {
        renderTitleGrid,
        renderPagination,
        renderSkeletons,
        renderErrorState,
        renderEmptyState,
        renderModal,
        renderStatsSummary,
        renderComparisonCards,
        populateSelect,
    };
})();
