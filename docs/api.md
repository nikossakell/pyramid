# API

> Status: outline. Generated reference is served at `/docs` (development only).

All endpoints are prefixed with `/api`. Authentication is a bearer JWT obtained
from `/api/auth/login` with a pre-issued access key.

## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/login` | Access key -> JWT. There is no registration endpoint. |
| POST | `/api/auth/logout` | |

## Users

| Method | Path | Notes |
|---|---|---|
| GET | `/api/users/me` | |
| PATCH | `/api/users/me` | |

## Meals

| Method | Path | Notes |
|---|---|---|
| POST | `/api/meals/photo` | Raw `image/jpeg` body, <= 1 MB. Returns a `PhotoResult`; nothing is stored. |
| POST | `/api/meals/text` | Free Greek text -> extracted foods. |
| POST | `/api/meals/confirm` | `MealConfirmation` -- the child's corrected list is what gets persisted. |
| GET | `/api/meals` | History. |

## Recommendations

| Method | Path | Notes |
|---|---|---|
| GET | `/api/recommendations/daily` | Daily summary. |

## Ask

| Method | Path | Notes |
|---|---|---|
| POST | `/api/ask` | Educational question -> answer with sources. |

## Game

| Method | Path | Notes |
|---|---|---|
| GET | `/api/game/cards` | |
| GET | `/api/game/deck` | |
| POST | `/api/game/battle` | Against the CPU. No leaderboards exist. |

## Admin (VPN only)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/admin/alerts` | |
| GET | `/api/admin/monitoring` | |

## Webhooks

| Method | Path | Notes |
|---|---|---|
| POST | `/api/webhooks/game` | Unity iframe events. |
