/**
 * Turn recap view — reverse-chronological list of turn narrations.
 */

// eslint-disable-next-line no-unused-vars
async function renderRecap(container) {
    container.innerHTML = '<p class="loading-text">Loading recap...</p>';

    const campaignId = (typeof AppState !== 'undefined' && AppState.campaignId) || null;

    // If we don't have a campaign ID, try to get it from the page or show empty state
    if (!campaignId) {
        container.innerHTML = `
            <div class="card">
                <div class="card-title">Turn Recap</div>
                <p class="empty-state">No campaign active.</p>
            </div>
        `;
        return;
    }

    const data = await API.getRecap(campaignId, 20);
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load recap.</p>';
        return;
    }

    const entries = data.entries || [];
    if (entries.length === 0) {
        container.innerHTML = `
            <div class="card">
                <div class="card-title">Turn Recap</div>
                <p class="empty-state">No turns played yet.</p>
            </div>
        `;
        return;
    }

    var entriesHtml = entries.map(function (entry) {
        var timeStr = '';
        if (entry.committed_at) {
            try {
                var d = new Date(entry.committed_at);
                timeStr = formatRelativeTime(d);
            } catch (e) {
                timeStr = entry.committed_at;
            }
        }

        return '<div class="recap-entry card">' +
            '<div class="recap-header">' +
                '<span class="recap-turn-badge">Turn ' + entry.turn_number + '</span>' +
                '<span class="recap-scene">' + escapeHtml(entry.scene_name || '') + '</span>' +
            '</div>' +
            '<div class="recap-narration">' + escapeHtml(entry.narration || '') + '</div>' +
            (timeStr ? '<div class="recap-time">' + escapeHtml(timeStr) + '</div>' : '') +
        '</div>';
    }).join('');

    container.innerHTML =
        '<div class="card-title" style="margin-bottom:12px">Turn Recap</div>' +
        entriesHtml;
}

function formatRelativeTime(date) {
    var now = new Date();
    var diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' minutes ago';
    if (diff < 86400) return Math.floor(diff / 3600) + ' hours ago';
    return Math.floor(diff / 86400) + ' days ago';
}
