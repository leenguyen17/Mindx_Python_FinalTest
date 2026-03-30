/**
 * Netflix Data Explorer — API Client
 * Handles all fetch requests with API key auth and error handling.
 */

const API = (() => {
    const API_KEY = window.__API_KEY__ || '';

    const headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
    };

    async function request(url) {
        const res = await fetch(url, { headers });

        if (res.status === 401) {
            window.location.href = '/login';
            throw new Error('Authentication required');
        }

        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error(body.error || `Request failed (${res.status})`);
        }

        return res.json();
    }

    function buildQuery(params) {
        const qs = new URLSearchParams();
        for (const [key, val] of Object.entries(params)) {
            if (val !== '' && val !== null && val !== undefined) {
                qs.set(key, val);
            }
        }
        return qs.toString();
    }

    return {
        async fetchTitles(params = {}) {
            const qs = buildQuery(params);
            return request(`/api/titles?${qs}`);
        },

        async fetchTitle(showId) {
            return request(`/api/titles/${encodeURIComponent(showId)}`);
        },

        async fetchFilters() {
            return request('/api/filters');
        },

        async fetchStats() {
            return request('/api/stats');
        },

        async fetchAnalysis(params = {}) {
            const qs = buildQuery(params);
            return request(`/api/analysis?${qs}`);
        },

        getExportPdfUrl(params = {}) {
            const qs = buildQuery({ ...params, api_key: API_KEY });
            return `/api/export/pdf?${qs}`;
        },

        getExportStatsPdfUrl() {
            return `/api/export/stats-pdf?api_key=${API_KEY}`;
        },

        getExportAnalysisPdfUrl(params = {}) {
            const qs = buildQuery({ ...params, api_key: API_KEY });
            return `/api/export/analysis-pdf?${qs}`;
        },
    };
})();
