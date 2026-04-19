# Mini App Architecture

## Overview

The Mini App is a single-page web application served by a local HTTP server.
Telegram's WebApp API provides the launch context (user identity, theme,
viewport size). The Mini App communicates with the game server via a REST API.

## Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| HTTP server | FastAPI | Lightweight, async, serves both API and static files |
| Frontend | Vanilla HTML/CSS/JS | No build step, minimal dependencies, Telegram WebApp SDK compatible |
| Auth | Telegram WebApp.initData | Validates user identity via HMAC; no separate auth system needed |
| Styling | CSS custom properties | Inherits Telegram theme colors via WebApp API |

## Launch Flow

1. Player taps an inline button in Telegram (e.g. "Open Sheet" on turn-control message)
2. Telegram opens the Mini App URL as a WebApp overlay
3. Mini App loads, reads `Telegram.WebApp.initData` for user identity
4. Mini App calls the game server API to fetch state
5. Mini App renders the requested view (sheet, inventory, recap)

## URL Scheme

| URL | View |
|---|---|
| /app/ | Main menu (links to all views) |
| /app/#sheet | Character sheet |
| /app/#inventory | Inventory |
| /app/#recap | Turn recap |
| /app/#quest-log | Quest log (Phase 18) |
| /app/#inbox | Private inbox (Phase 18) |
| /app/#action | Action builder (Phase 18) |

## API Endpoints (served by FastAPI)

| Method | Path | Purpose |
|---|---|---|
| GET | /api/player/{player_id} | Player info + character |
| GET | /api/character/{character_id} | Full character sheet |
| GET | /api/character/{character_id}/inventory | Character's items |
| GET | /api/scene/{scene_id} | Current scene state |
| GET | /api/campaign/{campaign_id}/recap | Recent turn log entries |
| POST | /api/auth/validate | Validate Telegram initData |

## Security

- All API endpoints validate that the requesting player can only access their own data
- initData is validated via HMAC-SHA256 using the bot token
- Scene data excludes hidden descriptions (referee-only content)
- Inventory only returns items owned by the requesting character
- Recap entries exclude referee-only facts
