# IRI voice workspace

React and Vite application using Peer Design and `@base-ui/react` 1.7.0.

```sh
npm ci
npm run dev
npm run build
```

The development server runs on `127.0.0.1:5173` and proxies `/api` to the local FastAPI server on port 8000. Production rewrites use the Contabo HTTPS virtual host in `vercel.json`. No client environment variables or API credentials are required.

Voice input uses MediaRecorder with WebM/Opus on Chrome and MP4 where supported. The user approves external processing before recording, then confirms or edits the transcript before sending. Recording stops at 60 seconds. The UI releases microphone tracks after recording. Silent input, missing microphone permission, API failure and blocked autoplay have separate recovery paths. Text input remains available and speech can be disabled in settings.

Peer Design sources used from the local reference repository:

- `DESIGN.md` and `styles/tokens.css` for square corners, colors, type and spacing.
- `examples/base-ui/components/button/demos/hero/css-modules/` for actions.
- `examples/base-ui/components/dialog/demos/hero/css-modules/` for portal, backdrop, title and focus behavior.
- `examples/base-ui/components/input/demos/hero/css-modules/` for the access code field.
- `examples/base-ui/components/radio/demos/hero/css-modules/` for age selection.
- `examples/base-ui/components/switch/demos/hero/css-modules/` for automatic speech.

The Base UI version matches the reference snapshot. Voice and mobile controls use larger touch targets. Font assets come from the same Peer Design reference. Layout was inspected at widths 320, 390, 820 and 1440 pixels, including a dark-mode settings dialog.

The browser flow was verified with synthetic speech routed through a real MediaRecorder and actual OpenAI services. Physical microphones, mobile Safari and speaker quality still need device testing.

Headless Chrome fault-injection checks also cover permission denial, cancellation while permission is pending, release of a late microphone stream, recording errors without an upload, TTS service failure, blocked autoplay with replay, and an expired speech session returning to login. Permission acquisition has a separate cancellable state; failed recordings are discarded. The pending-permission UI was visually checked at 320px and 1440px.
