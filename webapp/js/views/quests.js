/**
 * Quest log view — shows quests grouped by status.
 */

// eslint-disable-next-line no-unused-vars
async function renderQuestLog(container) {
    container.innerHTML = '<p class="loading-text">Loading quests...</p>';

    var campaignId = (typeof AppState !== 'undefined' && AppState.campaignId) || null;
    if (!campaignId) {
        container.innerHTML =
            '<div class="card">' +
                '<div class="card-title">Quest Log</div>' +
                '<p class="empty-state">No campaign active.</p>' +
            '</div>';
        return;
    }

    var data = await API.get('/api/campaign/' + campaignId + '/quests');
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load quests.</p>';
        return;
    }

    var quests = data.quests || [];
    if (quests.length === 0) {
        container.innerHTML =
            '<div class="card">' +
                '<div class="card-title">Quest Log</div>' +
                '<p class="empty-state">No quests yet.</p>' +
            '</div>';
        return;
    }

    // Group by status
    var groups = { active: [], completed: [], failed: [], inactive: [] };
    quests.forEach(function(q) {
        var status = q.status || 'inactive';
        if (groups[status]) groups[status].push(q);
        else groups.inactive.push(q);
    });

    var html = '';
    ['active', 'completed', 'failed', 'inactive'].forEach(function(status) {
        var list = groups[status];
        if (list.length === 0) return;
        html += '<div class="card"><div class="card-title">' +
                status.charAt(0).toUpperCase() + status.slice(1) + '</div>';
        list.forEach(function(q) {
            html += '<div class="item-card"><div style="flex:1">' +
                '<div class="item-name">' + escapeHtml(q.title) + '</div>' +
                '<div class="item-desc">' + escapeHtml(q.description || '') + '</div>' +
            '</div></div>';
        });
        html += '</div>';
    });

    container.innerHTML = html;
}
