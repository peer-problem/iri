# IRI demo deployment

The React application in `web/` is deployed to Vercel. Its `/api` rewrite targets the dedicated HTTPS virtual host `iri.5.104.87.93.sslip.io` on Contabo. No API or deployment secrets are compiled into browser JavaScript.

The API runs as the unprivileged `iri` account, bound to localhost port 8300. Nginx and systemd definitions are kept beside this file. Use one Uvicorn worker because anonymous sessions, limits and recent conversation context are stored in bounded process memory. Restarting the service clears those sessions. A production multi-worker deployment would require a shared session store.

Runtime configuration belongs in `/opt/iri/shared/api.env` (root-owned, mode 600). It contains only API runtime settings. Deployment tokens, SSH passwords, Runpod credentials and Hugging Face credentials stay local in `.keys/.env`.

From the repository root, install the locked Runpod environment and `sshpass` locally, then run `runpod/.venv/bin/python api/deploy/deploy.py vps` to publish a new Contabo release. Run `runpod/.venv/bin/python api/deploy/deploy.py vercel` to deploy the web app, followed by `runpod/.venv/bin/python api/deploy/deploy.py status` to check Vercel readiness. The runner reads `.keys/.env` and the pinned SSH host key at `.keys/contabo_known_hosts`. It uploads only the listed API runtime values to the VPS. Its Vercel deployment receipt is written under ignored `.logs/deploy/`.

Required runtime values include `SANDBOX_API_KEY`, `MODEL_API_KEY`, `MODEL_REVISION`, `MODEL_PROFILE=kanana`, `ADAPTER_NAME=iri-kanana3b-v5-0ecacdb7d7f7`, `ADAPTER_REVISION`, `ADAPTER_SHA256`, `MODEL_BASE_URL`, `OPENAI_API_KEY`, `ALLOWED_ORIGINS` and `SECURE_COOKIES=true`. Browser access is anonymous and does not use a participation code. The OpenAI key is for the Luna fallback, speech transcription and speech synthesis. Set `ALLOWED_ORIGINS` to the exact production Vercel origin. Local development uses `SECURE_COOKIES=false` and the two localhost origins from Settings.

Deployment layout: `/opt/iri/releases/<release>/api`, `/opt/iri/current` symlink and `/opt/iri/venv`. Retain the previous release for rollback. To roll back, repoint `current` to the recorded previous release and restart only `iri-api.service`.

The primary answer model is Kanana 3B. The base alias handles input and output checks while the versioned, hash-bound adapter alias handles generation. A 15-second primary-model deadline applies. If Kanana is unavailable, Luna high reruns the complete guarded pipeline and `/chat` reports `provider: "luna"`. If both providers fail, `/chat` returns 503 with `provider: "unavailable"`. Serving must expose both exact aliases. No GPU is automatically started by the application. The adapter release and manual serving procedure are in `runpod/HF_SERVING.md`.

### Connecting a resumed Kanana server

The Contabo configuration may point to `http://127.0.0.1:8002/v1`. This refers to the VPS itself, not the developer machine. Starting a Runpod model alone does not establish this connection; the product returns an unavailable response until the endpoint is reachable and ready.

Before resuming GPU serving, choose either an authenticated HTTPS model endpoint or a verified SSH tunnel running on Contabo and bound only to `127.0.0.1:8002`. Do not expose the model's unauthenticated HTTP port publicly. Set `MODEL_BASE_URL` and matching `MODEL_API_KEY` in the VPS runtime environment, preserving the pinned `MODEL_REVISION`. Restart only `iri-api.service` if its configuration changes. Keep the local deployment configuration consistent before a subsequent deploy overwrites runtime values.

Verify the product `/ready` endpoint from Contabo, then verify that a `/chat` response reports `provider: "kanana"`. `/health` only reports configuration, not an active model connection. When the serving connection disappears, `/ready` should return 503 and `/chat` should report `provider: "luna"`. If Luna is also unavailable, `/chat` returns 503 with `provider: "unavailable"`. The application neither creates nor starts GPU pods; GPU timing, backup and stop verification remain separate operator responsibilities.

Default audio models: `gpt-4o-mini-transcribe` and `gpt-4o-mini-tts-2025-12-15`. Audio consent and transcript confirmation happen before chat. Text answers remain available if speech generation or autoplay fails. Anonymous-cookie speech requests can read only recently checked assistant answers; the internal Bearer endpoint retains the trusted-client API contract.

Anonymous session creation is limited to 30 sessions per source address per 5 minutes. Each session is limited to 90 mutations per 10 minutes, with a 120-mutation source-address ceiling across sessions. These are single-process demo protections, not a global billing budget. Set account spending limits separately for public operation.

Sessions expire after one hour and are swept every 30 seconds. Recent history contains at most six turns. New conversation and age change discard that session history. The application does not persist recorded audio or conversations; external provider processing policies still apply.
