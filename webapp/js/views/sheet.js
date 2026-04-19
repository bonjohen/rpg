/**
 * Character sheet view — displays stats, status effects, health.
 */

// eslint-disable-next-line no-unused-vars
async function renderSheet(container) {
    container.innerHTML = '<p class="loading-text">Loading character...</p>';

    const charId = (typeof AppState !== 'undefined' && AppState.characterId) || null;
    if (!charId) {
        container.innerHTML = '<p class="empty-state">No character found. Join a game first.</p>';
        return;
    }

    const data = await API.getCharacter(charId);
    if (!data) {
        container.innerHTML = '<p class="empty-state">Could not load character data.</p>';
        return;
    }

    // Build stats grid
    const statsHtml = Object.entries(data.stats || {})
        .map(([key, val]) => `
            <div class="stat-item">
                <div class="stat-label">${escapeHtml(key)}</div>
                <div class="stat-value">${escapeHtml(String(val))}</div>
            </div>
        `).join('');

    // Status effects
    const effectsHtml = (data.status_effects || []).length > 0
        ? `<div class="tag-list">
            ${data.status_effects.map(e => `<span class="tag status-effect">${escapeHtml(e)}</span>`).join('')}
           </div>`
        : '<p style="color:var(--tg-hint);font-size:0.85rem">No active effects.</p>';

    // Health indicator
    const alive = data.is_alive !== false;
    const healthClass = alive ? '' : ' dead';
    const healthText = alive ? 'Alive' : 'Fallen';

    container.innerHTML = `
        <div class="card">
            <div class="card-title">${escapeHtml(data.name || 'Unknown')}</div>
            <div class="card-subtitle">Scene: ${escapeHtml(data.scene_id || 'None')}</div>
            <div class="health-indicator">
                <span class="health-dot${healthClass}"></span>
                <span class="health-label">${healthText}</span>
            </div>
        </div>

        <div class="card">
            <div class="card-title">Stats</div>
            <div class="stat-grid">${statsHtml || '<p class="empty-state">No stats.</p>'}</div>
        </div>

        <div class="card">
            <div class="card-title">Status Effects</div>
            ${effectsHtml}
        </div>
    `;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
