"""Deploy the IRI demo using credentials in the ignored .keys/.env."""

import argparse
import base64
import io
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
CONFIG = dotenv_values(ROOT / ".keys/.env")
PROJECT = "iri-voice"
PUBLIC_DOMAIN = "iri.today"
API_DOMAIN = f"api.{PUBLIC_DOMAIN}"
PRODUCTION_ORIGIN = f"https://{PUBLIC_DOMAIN}"
REQUIRED_RUNTIME = (
    "SANDBOX_API_KEY",
    "MODEL_API_KEY",
    "MODEL_REVISION",
    "MODEL_PROFILE",
    "ADAPTER_NAME",
    "ADAPTER_REVISION",
    "ADAPTER_SHA256",
    "MODEL_BASE_URL",
    "OPENAI_API_KEY",
)


def ssh(command, data=None, timeout=180):
    env = os.environ.copy()
    env["SSHPASS"] = CONFIG["CONTABO_VPS_PASSWORD"]
    args = [
        "sshpass",
        "-e",
        "ssh",
        "-o",
        "ConnectTimeout=10",
        "-o",
        f"UserKnownHostsFile={ROOT}/.keys/contabo_known_hosts",
        f"{CONFIG['CONTABO_VPS_DEFAULT_USER']}@{CONFIG['CONTABO_VPS_IP_ADDRESS']}",
        command,
    ]
    result = subprocess.run(
        args, input=data, capture_output=True, env=env, timeout=timeout, check=False
    )
    print(result.stdout.decode(), end="", flush=True)
    if result.returncode:
        print(result.stderr.decode(), flush=True)
        raise RuntimeError(f"SSH command failed ({result.returncode})")
    return result.stdout.decode()


def require_api_dns():
    expected_ip = CONFIG["CONTABO_VPS_IP_ADDRESS"]
    result = subprocess.run(
        ["dig", "+short", "A", API_DOMAIN, "@1.1.1.1"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Could not verify public DNS for {API_DOMAIN}")
    addresses = set(result.stdout.splitlines())
    if expected_ip not in addresses:
        raise RuntimeError(f"{API_DOMAIN} does not resolve to the configured Contabo VPS")


def require_runtime_config():
    missing = [key for key in REQUIRED_RUNTIME if not CONFIG.get(key)]
    if missing:
        raise RuntimeError(
            "Missing required deployment settings: " + ", ".join(missing)
        )


def vps(origin):
    require_runtime_config()
    require_api_dns()
    release = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    folder = f"/opt/iri/releases/{release}"
    ssh(
        f"set -eu; test ! -e {folder}; id iri >/dev/null 2>&1 || useradd --system --home /opt/iri --shell /usr/sbin/nologin iri; install -d -m 755 {folder} /opt/iri/shared /var/www/iri-acme"
    )
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        for directory in ("api",):
            for path in (ROOT / directory).rglob("*"):
                if (
                    path.is_file()
                    and "__pycache__" not in path.parts
                    and path.suffix in (".py", ".json", ".service", ".conf", ".sh")
                    and "tests" not in path.parts
                ):
                    tar.add(path, arcname=str(path.relative_to(ROOT)))
        for name in ("runpod/pyproject.toml", "runpod/uv.lock"):
            tar.add(ROOT / name, arcname=name)
    ssh(f"tar -xzf - -C {folder}", data.getvalue())
    runtime = {key: CONFIG[key] for key in REQUIRED_RUNTIME}
    runtime.update(
        SECURE_COOKIES="true",
        ALLOWED_ORIGINS=origin,
        STT_MODEL="gpt-4o-mini-transcribe",
        TTS_MODEL="gpt-4o-mini-tts-2025-12-15",
        TTS_VOICE="marin",
        TTS_SPEED="1.0",
        TTS_SEGMENT_MAX_CHARS="240",
        FALLBACK_MODEL="gpt-5.6-luna",
        FALLBACK_REASONING_EFFORT="high",
        BEHAVIOR_PROFILE="kanana_v5",
        REQUEST_TIMEOUT_SECONDS="90",
    )
    env_content = "".join(f"{k}={json.dumps(v)}\n" for k, v in runtime.items())
    ssh("umask 077; cat > /opt/iri/shared/api.env", env_content.encode())
    ssh(f"""set -eu
test -x /opt/iri/venv/bin/python || uv venv --python 3.12 /opt/iri/venv
uv export --frozen --no-dev --no-emit-project --project {folder}/runpod --output-file {folder}/requirements.txt >/dev/null
uv pip sync --link-mode copy --reinstall --python /opt/iri/venv/bin/python {folder}/requirements.txt
chown -R root:iri /opt/iri/venv
chmod -R g+rX /opt/iri/venv
chown -R root:iri {folder}
chmod -R g+rX {folder}
if test -L /opt/iri/current; then readlink /opt/iri/current; fi
ln -sfn {folder} /opt/iri/current
install -m 644 {folder}/api/deploy/iri-api.service /etc/systemd/system/iri-api.service
systemctl daemon-reload
systemctl enable iri-api.service
systemctl restart iri-api.service
""")
    ssh(f"""set -eu
if ! test -f /etc/letsencrypt/live/{API_DOMAIN}/fullchain.pem; then
 install -m 644 {folder}/api/deploy/nginx-http.conf /etc/nginx/sites-available/iri-api
 ln -sfn /etc/nginx/sites-available/iri-api /etc/nginx/sites-enabled/iri-api
 nginx -t
 systemctl reload nginx
 certbot certonly --webroot -w /var/www/iri-acme -d {API_DOMAIN} --non-interactive --agree-tos --register-unsafely-without-email
fi
install -m 644 {folder}/api/deploy/nginx.conf /etc/nginx/sites-available/iri-api
install -m 755 {folder}/api/deploy/renew-iri-cert.sh /etc/letsencrypt/renewal-hooks/deploy/iri-nginx
ln -sfn /etc/nginx/sites-available/iri-api /etc/nginx/sites-enabled/iri-api
nginx -t
systemctl reload nginx
systemctl is-active iri-api
curl -fsS --retry 8 --retry-connrefused --retry-delay 1 http://127.0.0.1:8300/health
""")
    print("VPS release:", release)


def ensure_public_domains(client, base, details):
    params = {"teamId": details["accountId"]}
    response = client.get(f"{base}/v9/projects/{details['id']}/domains", params=params)
    response.raise_for_status()
    domains = {item["name"]: item for item in response.json().get("domains", [])}
    expected = [
        {"name": PUBLIC_DOMAIN},
        {
            "name": f"www.{PUBLIC_DOMAIN}",
            "redirect": PUBLIC_DOMAIN,
            "redirectStatusCode": 308,
        },
    ]
    for desired in expected:
        current = domains.get(desired["name"])
        if current is None:
            added = client.post(
                f"{base}/v10/projects/{details['id']}/domains",
                params=params,
                json=desired,
            )
            added.raise_for_status()
            continue
        if any(current.get(key) != value for key, value in desired.items() if key != "name"):
            raise RuntimeError(f"Vercel domain settings differ for {desired['name']}")

    response = client.get(f"{base}/v4/domains/{PUBLIC_DOMAIN}/records", params=params)
    response.raise_for_status()
    records = response.json().get("records", [])
    api_records = [
        item for item in records if item.get("name") == "api" and item.get("type") == "A"
    ]
    expected_ip = CONFIG["CONTABO_VPS_IP_ADDRESS"]
    if not api_records:
        created = client.post(
            f"{base}/v2/domains/{PUBLIC_DOMAIN}/records",
            params=params,
            json={
                "name": "api",
                "type": "A",
                "value": expected_ip,
                "ttl": 60,
                "comment": "IRI production API on Contabo",
            },
        )
        created.raise_for_status()
    elif len(api_records) != 1 or api_records[0].get("value") != expected_ip:
        raise RuntimeError(f"DNS A record differs for {API_DOMAIN}")


def vercel_client():
    headers = {"Authorization": "Bearer " + CONFIG["VERCEL_DEPLOY_KEY"]}
    client = httpx.Client(headers=headers, timeout=120)
    base = "https://api.vercel.com"
    project = client.get(f"{base}/v9/projects/{PROJECT}")
    if project.status_code == 404:
        project = client.post(
            f"{base}/v10/projects", json={"name": PROJECT, "framework": "vite"}
        )
    project.raise_for_status()
    details = project.json()
    return client, base, details


def domains():
    client, base, details = vercel_client()
    try:
        ensure_public_domains(client, base, details)
    finally:
        client.close()
    print("Domains ready:", PUBLIC_DOMAIN, API_DOMAIN)


def vercel():
    client, base, details = vercel_client()
    try:
        print("Vercel project:", details["name"], details["id"], flush=True)
        ensure_public_domains(client, base, details)
        files = []
        web = ROOT / "web"
        for path in web.rglob("*"):
            relative = path.relative_to(web)
            if not path.is_file() or any(
                p in ("node_modules", "dist", ".vercel", "test-results")
                for p in relative.parts
            ):
                continue
            if relative.parts[0] not in ("src", "public", "scripts") and str(relative) not in (
                "package.json",
                "package-lock.json",
                "tsconfig.json",
                "vite.config.ts",
                "vercel.json",
                "index.html",
            ):
                continue
            files.append(
                {
                    "file": str(relative),
                    "data": base64.b64encode(path.read_bytes()).decode(),
                    "encoding": "base64",
                }
            )
        result = client.post(
            f"{base}/v13/deployments",
            json={
                "name": PROJECT,
                "project": details["id"],
                "target": "production",
                "files": files,
                "projectSettings": {
                    "framework": "vite",
                    "buildCommand": "npm run build",
                    "outputDirectory": "dist",
                    "installCommand": "npm ci",
                },
            },
        )
        if result.is_error:
            print(
                "Vercel error:",
                result.status_code,
                result.json().get("error", {}).get("message"),
            )
            result.raise_for_status()
        deployment = result.json()
        print("Deployment:", deployment["id"], deployment["url"], flush=True)
        record = ROOT / ".logs/deploy/vercel-deployment.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            json.dumps(
                {k: deployment.get(k) for k in ("id", "url", "readyState", "alias")},
                indent=2,
            )
        )
    finally:
        client.close()


def status():
    record_path = ROOT / ".logs/deploy/vercel-deployment.json"
    record = json.loads(record_path.read_text())
    response = httpx.get(
        "https://api.vercel.com/v13/deployments/" + record["id"],
        headers={"Authorization": "Bearer " + CONFIG["VERCEL_DEPLOY_KEY"]},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    snapshot = {
        k: data.get(k)
        for k in ("id", "url", "readyState", "alias", "errorMessage")
    }
    record_path.write_text(json.dumps(snapshot, indent=2))
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["domains", "vps", "vercel", "status"])
    parser.add_argument("--origin", default=PRODUCTION_ORIGIN)
    args = parser.parse_args()
    {
        "domains": domains,
        "vps": lambda: vps(args.origin),
        "vercel": vercel,
        "status": status,
    }[args.action]()
