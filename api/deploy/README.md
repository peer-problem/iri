# IRI demo deployment

The React application in `web/` is deployed to Vercel. Its `/api` rewrite targets the dedicated HTTPS virtual host `iri.5.104.87.93.sslip.io` on Contabo. No API or deployment secrets are compiled into browser JavaScript.

The API runs as the unprivileged `iri` account, bound to localhost port 8300. Nginx and systemd definitions are kept beside this file. Use one Uvicorn worker because demo sessions, limits and recent conversation context are stored in bounded process memory. Restarting the service signs participants out. A production multi-worker deployment would require a shared session store.

Runtime configuration belongs in `/opt/iri/shared/api.env` (root-owned, mode 600). It contains only API runtime settings. Deployment tokens, SSH passwords, Runpod credentials and Hugging Face credentials stay local in `.keys/.env`.

From the repository root, install the locked Runpod environment and `sshpass` locally, then run `runpod/.venv/bin/python api/deploy/deploy.py vps` to publish a new Contabo release. Run `runpod/.venv/bin/python api/deploy/deploy.py vercel` to deploy the web app, followed by `runpod/.venv/bin/python api/deploy/deploy.py status` to check Vercel readiness. The runner reads `.keys/.env` and the pinned SSH host key at `.keys/contabo_known_hosts`. It uploads only the listed API runtime values to the VPS. Its Vercel deployment receipt is written under ignored `.logs/deploy/`.

Required runtime values: `SANDBOX_API_KEY`, `MODEL_API_KEY`, `MODEL_REVISION`, `MODEL_BASE_URL`, `OPENAI_API_KEY`, `DEMO_ACCESS_CODE`, `ALLOWED_ORIGINS` and `SECURE_COOKIES=true`. Set `ALLOWED_ORIGINS` to the exact production Vercel origin. Local development uses `SECURE_COOKIES=false` and the two localhost origins from Settings.

Deployment layout: `/opt/iri/releases/<release>/api`, `/opt/iri/current` symlink and `/opt/iri/venv`. Retain the previous release for rollback. To roll back, repoint `current` to the recorded previous release and restart only `iri-api.service`.

The primary model is checked on demand, with a 2-second readiness timeout and a 15-second primary request deadline. After failure the entire input-check, generation and output-check sequence runs on `gpt-5.6-luna` with reasoning `high`. The primary is retried after 15 seconds. Serving must expose the configured pinned model alias. No GPU is automatically started by the application.

### Connecting a resumed Kanana server

The current Contabo configuration points to `http://127.0.0.1:8002/v1`, but no tunnel is listening there (checked September 17, 2026). This refers to the VPS itself, not the developer machine. Starting a Runpod model alone does not establish this connection; Luna remains active until the endpoint is reachable and ready.

Before resuming GPU serving, choose either an authenticated HTTPS model endpoint or a verified SSH tunnel running on Contabo and bound only to `127.0.0.1:8002`. Do not expose the model's unauthenticated HTTP port publicly. Set `MODEL_BASE_URL` and matching `MODEL_API_KEY` in the VPS runtime environment, preserving the pinned `MODEL_REVISION`. Restart only `iri-api.service` if its configuration changes. Keep the local deployment configuration consistent before a subsequent deploy overwrites runtime values.

Verify the authenticated product `/ready` endpoint from Contabo, then verify that a `/chat` response reports `provider: "kanana"`. `/health` only reports configuration, not an active model connection. When the serving connection disappears, a checked Luna response should report `provider: "luna"`. The application neither creates nor starts GPU pods; GPU timing, backup and stop verification remain separate operator responsibilities.

Default audio models: `gpt-4o-mini-transcribe` and `gpt-4o-mini-tts-2025-12-15`. Audio consent and transcript confirmation happen before chat. Text answers remain available if speech generation or autoplay fails. Demo-cookie speech requests can read only recently checked assistant answers; the internal Bearer endpoint retains the trusted-client API contract.

Login is limited to 10 attempts per source address per 5 minutes. Each session is limited to 90 authenticated mutations per 10 minutes. These are single-process demo protections, not a global billing budget. Set account spending limits separately if opening the demo to a broad audience.

Sessions expire after one hour and are swept every 30 seconds. Recent history contains at most six turns. New conversation, age change and logout discard that session history. The application does not persist recorded audio or conversations; external provider processing policies still apply.
