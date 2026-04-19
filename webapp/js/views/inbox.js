/**
 * Private inbox view — shows private-referee messages for the player.
 */

// eslint-disable-next-line no-unused-vars
async function renderInbox(container) {
    container.innerHTML = '<p class="loading-text">Loading inbox...</p>';

    var playerId = (typeof AppState !== 'undefined' && AppState.playerId) || null;
    if (!playerId) {
        container.innerHTML = '<p class="empty-state">Not logged in.</p>';
        return;
    }

    var data = await API.get('/api/player/' + playerId + '/inbox');
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load inbox.</p>';
        return;
    }

    var messages = data.messages || [];
    if (messages.length === 0) {
        container.innerHTML =
            '<div class="card">' +
                '<div class="card-title">Private Inbox</div>' +
                '<p class="empty-state">No messages.</p>' +
            '</div>';
        return;
    }

    var unreadBadge = data.unread_count > 0
        ? ' <span class="tag">' + data.unread_count + ' new</span>'
        : '';

    var msgsHtml = messages.map(function(msg) {
        var readClass = msg.is_read ? '' : ' style="border-left:3px solid var(--tg-link)"';
        return '<div class="item-card"' + readClass + '>' +
            '<div style="flex:1">' +
                '<div class="item-name">' +
                    '<span class="tag status-effect">' + escapeHtml(msg.fact_type) + '</span> ' +
                    escapeHtml(msg.scene_name) +
                '</div>' +
                '<div class="item-desc" style="margin-top:4px">' + escapeHtml(msg.payload) + '</div>' +
                '<div class="recap-time">' + escapeHtml(msg.revealed_at || '') + '</div>' +
            '</div>' +
        '</div>';
    }).join('');

    container.innerHTML =
        '<div class="card">' +
            '<div class="card-title">Private Inbox' + unreadBadge + '</div>' +
            msgsHtml +
        '</div>';
}
