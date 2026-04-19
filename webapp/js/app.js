/**
 * RPG Mini App — main application controller.
 *
 * Initialises the Telegram WebApp SDK, manages hash-based routing,
 * and provides an API client wrapper used by all view modules.
 */

// ---------------------------------------------------------------------------
// Telegram WebApp SDK
// ---------------------------------------------------------------------------

const tg = window.Telegram && window.Telegram.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

const API = {
    /**
     * GET helper — returns parsed JSON or null on error.
     */
    async get(path) {
        try {
            const resp = await fetch(path);
            if (!resp.ok) return null;
            return await resp.json();
        } catch {
            return null;
        }
    },

    /**
     * POST helper — sends JSON body, returns parsed JSON or null.
     */
    async post(path, body) {
        try {
            const resp = await fetch(path, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!resp.ok) return null;
            return await resp.json();
        } catch {
            return null;
        }
    },

    // Convenience wrappers for game endpoints
    getPlayer(playerId) { return this.get(`/api/player/${playerId}`); },
    getCharacter(charId) { return this.get(`/api/character/${charId}`); },
    getInventory(charId) { return this.get(`/api/character/${charId}/inventory`); },
    getScene(sceneId) { return this.get(`/api/scene/${sceneId}`); },
    getRecap(campaignId, limit) {
        const q = limit ? `?limit=${limit}` : '';
        return this.get(`/api/campaign/${campaignId}/recap${q}`);
    },
};

// ---------------------------------------------------------------------------
// State — populated after auth
// ---------------------------------------------------------------------------

const AppState = {
    playerId: null,
    characterId: null,
    sceneId: null,
    campaignId: null,
};

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

const views = {
    menu: renderMenu,
    sheet: typeof renderSheet === 'function' ? renderSheet : () => {},
    inventory: typeof renderInventory === 'function' ? renderInventory : () => {},
    recap: typeof renderRecap === 'function' ? renderRecap : () => {},
    action: typeof renderActionBuilder === 'function' ? renderActionBuilder : () => {},
    inbox: typeof renderInbox === 'function' ? renderInbox : () => {},
    channels: typeof renderChannels === 'function' ? renderChannels : () => {},
    quests: typeof renderQuestLog === 'function' ? renderQuestLog : () => {},
    clues: typeof renderClueJournal === 'function' ? renderClueJournal : () => {},
    map: typeof renderMap === 'function' ? renderMap : () => {},
};

function getHash() {
    return (location.hash || '#menu').slice(1);
}

function navigate() {
    const view = getHash();
    const content = document.getElementById('app-content');
    if (!content) return;

    // Update nav active state
    document.querySelectorAll('.nav-link').forEach(link => {
        const target = link.getAttribute('href').slice(1);
        link.classList.toggle('active', target === view);
    });

    // Render the view
    const renderFn = views[view];
    if (renderFn) {
        renderFn(content);
    } else {
        content.innerHTML = '<p class="empty-state">View not found.</p>';
    }
}

window.addEventListener('hashchange', navigate);

// ---------------------------------------------------------------------------
// Menu view
// ---------------------------------------------------------------------------

function renderMenu(container) {
    container.innerHTML = `
        <div class="menu-grid">
            <a href="#sheet" class="menu-item">
                <span class="menu-icon">&#x1F9D9;</span>
                <span class="menu-label">Character</span>
            </a>
            <a href="#inventory" class="menu-item">
                <span class="menu-icon">&#x1F392;</span>
                <span class="menu-label">Inventory</span>
            </a>
            <a href="#recap" class="menu-item">
                <span class="menu-icon">&#x1F4DC;</span>
                <span class="menu-label">Recap</span>
            </a>
            <a href="#action" class="menu-item">
                <span class="menu-icon">&#x2694;</span>
                <span class="menu-label">Actions</span>
            </a>
            <a href="#inbox" class="menu-item">
                <span class="menu-icon">&#x1F4E8;</span>
                <span class="menu-label">Inbox</span>
            </a>
            <a href="#channels" class="menu-item">
                <span class="menu-icon">&#x1F4AC;</span>
                <span class="menu-label">Channels</span>
            </a>
            <a href="#quests" class="menu-item">
                <span class="menu-icon">&#x1F4CB;</span>
                <span class="menu-label">Quests</span>
            </a>
            <a href="#map" class="menu-item">
                <span class="menu-icon">&#x1F5FA;</span>
                <span class="menu-label">Map</span>
            </a>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
    // Try to get player info from Telegram initData
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
        AppState.playerId = String(tg.initDataUnsafe.user.id);
    }

    // If we have a player, hydrate state
    if (AppState.playerId) {
        const player = await API.getPlayer(AppState.playerId);
        if (player) {
            AppState.characterId = player.character_id;
            AppState.sceneId = player.current_scene_id;
        }
    }

    navigate();
}

init();
