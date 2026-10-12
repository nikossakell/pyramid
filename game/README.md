# Card game (Unity, WebGL)

## Layout

```
game/
├── unity_project/     # Unity editor project (source)
└── webgl_build/       # compiled WebGL output, served by Nginx at /game/
```

The compiled build (`webgl_build/Build/game.data`, `game.framework.js`,
`game.wasm`) is a build artefact and is gitignored.

## Building

1. Open `unity_project/` in the Unity editor.
2. Build target: WebGL, compression disabled (Nginx handles gzip).
3. Output directory: `../webgl_build`.

## How it talks to the app

The game runs in an iframe (`frontend/src/components/GameFrame.vue`) and
exchanges `postMessage` events with the PWA; the backend side is
`backend/app/api/webhooks.py`. Cards are granted by the rule engine
(`rule_engine/card_rules.py`) and dropped nightly by
`app/jobs/daily_card_drops.py`.

Battles are against the CPU only. There are no leaderboards and no
child-to-child comparison, by design.
