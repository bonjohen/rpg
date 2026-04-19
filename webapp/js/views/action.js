/**
 * Action builder view — compose and submit actions from the Mini App.
 */

// eslint-disable-next-line no-unused-vars
async function renderActionBuilder(container) {
    container.innerHTML = '<p class="loading-text">Loading action builder...</p>';

    var charId = (typeof AppState !== 'undefined' && AppState.characterId) || null;
    var sceneId = (typeof AppState !== 'undefined' && AppState.sceneId) || null;
    var playerId = (typeof AppState !== 'undefined' && AppState.playerId) || null;

    if (!charId || !sceneId) {
        container.innerHTML = '<p class="empty-state">No active scene. Join a game first.</p>';
        return;
    }

    var ctx = await API.get('/api/scene/' + sceneId + '/context');
    if (!ctx) {
        container.innerHTML = '<p class="empty-state">Could not load scene context.</p>';
        return;
    }

    // Build action type options
    var actionTypes = ['move', 'inspect', 'search', 'interact', 'attack', 'defend',
                       'use_item', 'question', 'persuade', 'threaten', 'custom'];

    var typeOptions = actionTypes.map(function(t) {
        return '<option value="' + t + '">' + t.replace('_', ' ') + '</option>';
    }).join('');

    // Build exit buttons for move
    var exitButtons = (ctx.exits || []).map(function(e) {
        return '<button class="tag" data-direction="' + escapeHtml(e.direction) +
               '" onclick="selectExit(this)">' + escapeHtml(e.direction) +
               ' (' + escapeHtml(e.target_scene_name) + ')</button>';
    }).join(' ');

    // Build target options
    var targetOptions = '<option value="">-- none --</option>';
    (ctx.targets || []).forEach(function(t) {
        targetOptions += '<option value="' + escapeHtml(t.target_id) + '">' +
                         escapeHtml(t.name) + ' (' + t.target_type + ')</option>';
    });

    container.innerHTML =
        '<div class="card">' +
            '<div class="card-title">Action Builder</div>' +
            '<div class="card-subtitle">' + escapeHtml(ctx.scene_name || '') + '</div>' +
            '<label class="form-label">Action Type</label>' +
            '<select id="action-type" class="form-select" onchange="onActionTypeChange()">' + typeOptions + '</select>' +
            '<div id="move-exits" style="display:none;margin-top:8px">' +
                '<label class="form-label">Direction</label>' +
                '<div class="tag-list">' + exitButtons + '</div>' +
                '<input type="hidden" id="movement-target" />' +
            '</div>' +
            '<div id="target-select" style="margin-top:8px">' +
                '<label class="form-label">Target</label>' +
                '<select id="action-target" class="form-select">' + targetOptions + '</select>' +
            '</div>' +
            '<label class="form-label" style="margin-top:8px">Description</label>' +
            '<textarea id="public-text" class="form-input" placeholder="What do you do?"></textarea>' +
            '<label class="form-label" style="margin-top:8px">Private note to referee</label>' +
            '<textarea id="private-text" class="form-input" placeholder="(optional)"></textarea>' +
            '<div style="margin-top:12px;display:flex;gap:8px">' +
                '<button class="btn btn-primary" onclick="submitAction()">Submit Action</button>' +
            '</div>' +
        '</div>';
}

function onActionTypeChange() {
    var type = document.getElementById('action-type').value;
    var moveExits = document.getElementById('move-exits');
    if (moveExits) moveExits.style.display = type === 'move' ? 'block' : 'none';
}

function selectExit(btn) {
    var input = document.getElementById('movement-target');
    if (input) input.value = btn.getAttribute('data-direction');
    document.querySelectorAll('#move-exits .tag').forEach(function(b) {
        b.style.opacity = '0.5';
    });
    btn.style.opacity = '1';
}

async function submitAction() {
    var playerId = (typeof AppState !== 'undefined' && AppState.playerId) || '';
    var type = document.getElementById('action-type').value;
    var target = document.getElementById('action-target').value;
    var publicText = document.getElementById('public-text').value;
    var privateText = document.getElementById('private-text').value;
    var movementTarget = document.getElementById('movement-target')
        ? document.getElementById('movement-target').value : '';

    // Find active turn window from scene context
    var sceneId = (typeof AppState !== 'undefined' && AppState.sceneId) || '';
    var ctx = await API.get('/api/scene/' + sceneId + '/context');
    var twId = ctx ? ctx.active_turn_window_id : '';

    if (!twId) {
        alert('No active turn window.');
        return;
    }

    var result = await API.post('/api/action/submit', {
        player_id: playerId,
        turn_window_id: twId,
        action_type: type,
        target_id: target,
        public_text: publicText,
        private_ref_text: privateText,
        movement_target: movementTarget
    });

    if (result && result.accepted) {
        alert('Action submitted!');
    } else {
        alert('Rejected: ' + (result ? result.rejection_reason : 'Unknown error'));
    }
}
