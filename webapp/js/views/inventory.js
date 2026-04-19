/**
 * Inventory view — displays items owned by the character.
 */

// eslint-disable-next-line no-unused-vars
async function renderInventory(container) {
    container.innerHTML = '<p class="loading-text">Loading inventory...</p>';

    const charId = (typeof AppState !== 'undefined' && AppState.characterId) || null;
    if (!charId) {
        container.innerHTML = '<p class="empty-state">No character found. Join a game first.</p>';
        return;
    }

    const data = await API.getInventory(charId);
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load inventory.</p>';
        return;
    }

    const items = data.items || [];
    if (items.length === 0) {
        container.innerHTML = `
            <div class="card">
                <div class="card-title">Inventory</div>
                <p class="empty-state">No items.</p>
            </div>
        `;
        return;
    }

    const itemsHtml = items.map(function (item) {
        const qtyBadge = item.quantity > 1
            ? '<span class="item-qty">x' + item.quantity + '</span>'
            : '';

        // Render key properties as tags
        const props = item.properties || {};
        const propTags = Object.entries(props)
            .filter(function (entry) { return entry[0] !== 'description'; })
            .map(function (entry) {
                return '<span class="tag">' + escapeHtml(entry[0] + ': ' + entry[1]) + '</span>';
            }).join('');

        return '<div class="item-card">' +
            '<div style="flex:1">' +
                '<div class="item-name">' + escapeHtml(item.name) + ' ' + qtyBadge + '</div>' +
                '<div class="item-desc">' + escapeHtml(item.description || '') + '</div>' +
                (propTags ? '<div class="tag-list" style="margin-top:4px">' + propTags + '</div>' : '') +
            '</div>' +
        '</div>';
    }).join('');

    container.innerHTML =
        '<div class="card">' +
            '<div class="card-title">Inventory</div>' +
            itemsHtml +
        '</div>';
}
