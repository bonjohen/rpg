/**
 * Clue journal view — shows discovered clues grouped by scene.
 */

// eslint-disable-next-line no-unused-vars
async function renderClueJournal(container) {
    container.innerHTML = '<p class="loading-text">Loading clues...</p>';

    var playerId = (typeof AppState !== 'undefined' && AppState.playerId) || null;
    if (!playerId) {
        container.innerHTML = '<p class="empty-state">Not logged in.</p>';
        return;
    }

    var data = await API.get('/api/player/' + playerId + '/clues');
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load clues.</p>';
        return;
    }

    var clues = data.clues || [];
    if (clues.length === 0) {
        container.innerHTML =
            '<div class="card">' +
                '<div class="card-title">Clue Journal</div>' +
                '<p class="empty-state">No clues discovered yet.</p>' +
            '</div>';
        return;
    }

    // Group by scene
    var byScene = {};
    clues.forEach(function(c) {
        var key = c.scene_name || 'Unknown';
        if (!byScene[key]) byScene[key] = [];
        byScene[key].push(c);
    });

    var html = '';
    Object.keys(byScene).forEach(function(sceneName) {
        html += '<div class="card"><div class="card-title">' + escapeHtml(sceneName) + '</div>';
        byScene[sceneName].forEach(function(c) {
            html += '<div class="item-card"><div style="flex:1">' +
                '<div class="item-desc">' + escapeHtml(c.payload) + '</div>' +
                '<div class="recap-time">' + escapeHtml(c.discovered_at || '') + '</div>' +
            '</div></div>';
        });
        html += '</div>';
    });

    container.innerHTML = html;
}
