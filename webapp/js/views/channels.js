/**
 * Side-channel management view — list, create, and interact with channels.
 */

// eslint-disable-next-line no-unused-vars
async function renderChannels(container) {
    container.innerHTML = '<p class="loading-text">Loading channels...</p>';

    var playerId = (typeof AppState !== 'undefined' && AppState.playerId) || null;
    if (!playerId) {
        container.innerHTML = '<p class="empty-state">Not logged in.</p>';
        return;
    }

    var data = await API.get('/api/player/' + playerId + '/channels');
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load channels.</p>';
        return;
    }

    var channels = data.channels || [];
    var channelsHtml = '';

    if (channels.length === 0) {
        channelsHtml = '<p class="empty-state">No channels.</p>';
    } else {
        channelsHtml = channels.map(function(ch) {
            var statusTag = ch.is_open
                ? '<span class="tag">open</span>'
                : '<span class="tag status-dead">closed</span>';
            return '<div class="item-card">' +
                '<div style="flex:1">' +
                    '<div class="item-name">' + escapeHtml(ch.label) + ' ' + statusTag + '</div>' +
                    '<div class="item-desc">Members: ' + ch.members.map(escapeHtml).join(', ') + '</div>' +
                    '<div class="recap-time">' + ch.message_count + ' messages</div>' +
                '</div>' +
            '</div>';
        }).join('');
    }

    container.innerHTML =
        '<div class="card">' +
            '<div class="card-title">Side Channels</div>' +
            channelsHtml +
        '</div>';
}
