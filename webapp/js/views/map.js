/**
 * Map view — simple SVG node-link diagram of discovered scenes.
 */

// eslint-disable-next-line no-unused-vars
async function renderMap(container) {
    container.innerHTML = '<p class="loading-text">Loading map...</p>';

    var campaignId = (typeof AppState !== 'undefined' && AppState.campaignId) || null;
    var playerId = (typeof AppState !== 'undefined' && AppState.playerId) || '';

    if (!campaignId) {
        container.innerHTML =
            '<div class="card">' +
                '<div class="card-title">Map</div>' +
                '<p class="empty-state">No campaign active.</p>' +
            '</div>';
        return;
    }

    var data = await API.get('/api/campaign/' + campaignId + '/map?player_id=' + playerId);
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load map.</p>';
        return;
    }

    var nodes = data.nodes || [];
    var edges = data.edges || [];

    if (nodes.length === 0) {
        container.innerHTML =
            '<div class="card">' +
                '<div class="card-title">Map</div>' +
                '<p class="empty-state">No areas discovered yet.</p>' +
            '</div>';
        return;
    }

    // Simple grid layout for SVG
    var svgW = 400;
    var svgH = Math.max(200, nodes.length * 80);
    var nodeRadius = 30;

    // Position nodes in a column layout
    var positions = {};
    nodes.forEach(function(n, i) {
        var x = 100 + (i % 3) * 120;
        var y = 60 + Math.floor(i / 3) * 100;
        positions[n.scene_id] = { x: x, y: y };
    });

    // Build SVG
    var svg = '<svg width="' + svgW + '" height="' + svgH + '" viewBox="0 0 ' + svgW + ' ' + svgH + '">';

    // Draw edges
    edges.forEach(function(e) {
        var from = positions[e.from_scene_id];
        var to = positions[e.to_scene_id];
        if (from && to) {
            var color = e.discovered ? 'var(--tg-link)' : 'var(--tg-hint)';
            svg += '<line x1="' + from.x + '" y1="' + from.y + '" x2="' + to.x + '" y2="' + to.y + '" stroke="' + color + '" stroke-width="2" />';
            // Direction label
            var mx = (from.x + to.x) / 2;
            var my = (from.y + to.y) / 2;
            svg += '<text x="' + mx + '" y="' + (my - 5) + '" font-size="10" fill="var(--tg-hint)" text-anchor="middle">' + escapeHtml(e.direction) + '</text>';
        }
    });

    // Draw nodes
    nodes.forEach(function(n) {
        var pos = positions[n.scene_id];
        if (!pos) return;
        var isCurrent = n.scene_id === data.current_scene_id;
        var fill = isCurrent ? 'var(--tg-button)' : (n.discovered ? 'var(--tg-secondary-bg)' : 'var(--tg-hint)');
        var textFill = isCurrent ? 'var(--tg-button-text)' : 'var(--tg-text)';
        svg += '<circle cx="' + pos.x + '" cy="' + pos.y + '" r="' + nodeRadius + '" fill="' + fill + '" stroke="var(--tg-text)" stroke-width="1" />';
        var label = n.discovered ? n.name : '?';
        svg += '<text x="' + pos.x + '" y="' + (pos.y + 4) + '" font-size="11" fill="' + textFill + '" text-anchor="middle">' + escapeHtml(label) + '</text>';
    });

    svg += '</svg>';

    container.innerHTML =
        '<div class="card">' +
            '<div class="card-title">Map</div>' +
            '<div style="overflow-x:auto">' + svg + '</div>' +
        '</div>';
}
