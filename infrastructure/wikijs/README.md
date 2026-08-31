# Wiki.js infrastructure

This directory adds an optional, isolated Wiki.js 2.x stack to Enhanced Pi Monitor. It does not containerize, replace, or change how the existing Flask process is deployed.

## Architecture and ports

```text
browser
  |-- existing hostname ----------> nginx (if configured) -> Flask :5000
  `-- wiki hostname or :3000 -----> nginx (optional) ------> Wiki.js :3000
                                                              |
                                                              `-> PostgreSQL :5432 (private Docker network only)
```

| Service | Image | Host exposure | Persistence |
| --- | --- | --- | --- |
| `wikijs` | `ghcr.io/requarks/wiki:2.5.314` by default | `127.0.0.1:3000` by default | `wikijs-content` at `/wiki/data/content` |
| `wikijs-db` | `postgres:16-alpine` | none | `wikijs-db-data` at `/var/lib/postgresql/data` |

The database is attached only to an internal Docker network. Wiki.js also joins a normal frontend network so it can retrieve localization/update metadata. Uploaded assets and pages are stored in PostgreSQL by Wiki.js; the content volume also preserves local storage/synchronization state if that feature is enabled later.

## Prerequisites

- Docker Engine with the Docker Compose v2 plugin (`docker compose version`)
- `make` for the convenience commands, or direct `docker compose` use
- `openssl` to generate a database password
- Enough memory for PostgreSQL and Wiki.js in addition to the existing monitoring/ML processes

The pinned Wiki.js image supports x86-64 and ARM64. On Raspberry Pi, check `uname -m`: use a 64-bit OS reporting `aarch64`. Upstream dropped ARMv7 after Wiki.js 2.5.303, so upgrading the OS/device is preferable to pinning an older security-sensitive Wiki release.

## Configure and start

From the repository root:

```sh
cp infrastructure/wikijs/.env.example infrastructure/wikijs/.env
chmod 600 infrastructure/wikijs/.env
openssl rand -base64 48
```

Put the generated value in `WIKIJS_DB_PASSWORD`; Compose intentionally rejects the empty example value. Then run:

```sh
make wiki-up
make wiki-status
make wiki-logs
```

On the server itself, open `http://127.0.0.1:3000`. Complete the first-run wizard by creating the administrator account and setting the site URL to the exact URL browsers will use.

For initial access from another LAN or Tailscale device, either use an SSH tunnel (safer) or set the bind address deliberately:

```sh
ssh -L 3000:127.0.0.1:3000 user@SERVER_IP
```

Then open `http://127.0.0.1:3000` locally. Alternatively, set `WIKIJS_BIND_ADDRESS=0.0.0.0` (or the server's Tailscale IP) in `infrastructure/wikijs/.env`, restart the stack, and open `http://SERVER_IP:3000`. If binding all interfaces, restrict port 3000 with the host firewall. PostgreSQL remains unexposed in either mode.

## Day-to-day commands

```sh
make wiki-up
make wiki-down
make wiki-logs
make wiki-restart
make wiki-status
make wiki-pull
```

`wiki-down` removes the containers and networks but intentionally retains both named volumes. Do not add `--volumes` unless you explicitly intend to remove the Wiki.js data.

## Flask and exporter configuration

The Compose `.env` is only for infrastructure. The Flask process and exporter read these process environment variables:

| Variable | Required | Purpose |
| --- | --- | --- |
| `WIKIJS_URL` | no for Flask UI; yes for export | Public Wiki.js base URL, without `/graphql` |
| `WIKIJS_API_TOKEN` | only for backend extraction | Bearer token; never passed to a template or browser |
| `WIKIJS_LOCALE` | no | Locale queried by the source, default `en` |
| `WIKIJS_TIMEOUT_SECONDS` | no | GraphQL request timeout, default `10` |

Copy the repository `.env.example` if useful, then export it in the service environment. The application deliberately does not auto-load dotenv files. For systemd, an appropriate pattern is an owner-readable `EnvironmentFile` plus:

```ini
Environment="WIKIJS_URL=https://wiki.your-domain.example"
EnvironmentFile=/path/outside/git/pimonitor.env
```

When `WIKIJS_URL` is missing or invalid, Flask starts without Wiki integration and the dashboard card remains hidden. When configured, the card uses the JWT-protected `/wiki` route before redirecting to Wiki.js; no link is shown in the public portfolio. Wiki.js retains its own authentication boundary. `WIKIJS_API_TOKEN` is not present in Flask template context.

## Enable the Wiki.js API

The pinned Wiki.js 2.x release exposes a GraphQL API at `/graphql`. The client queries only fields in the [upstream 2.5.314 page schema](https://github.com/requarks/wiki/blob/v2.5.314/server/graph/schemas/page.graphql); Wiki.js also provides an [official GraphQL API overview](https://docs.requarks.io/dev/api).

1. Sign in as the Wiki.js administrator.
2. Open **Administration → API Access** and enable API access.
3. Create a dedicated extraction group with `read:pages` and `read:source`, plus page rules covering only the paths to export.
4. Create an API key for that group and copy it immediately.
5. Store it as `WIKIJS_API_TOKEN` only in the Flask/export process environment.
6. Test with the exporter below.

Wiki.js 2.x has had upstream permission inconsistencies around `pages.single`. If listing works but page retrieval returns a `6013` authorization error, re-check the group system permissions and page rules in the installed release. Do not grant write/delete permissions silently; decide explicitly whether a broader token is acceptable for this personal backend and keep that token out of browser-facing code.

Export all readable pages:

```sh
python3 scripts/export_wiki_knowledge.py --output data/wiki_export.jsonl
```

Incremental export by Wiki.js `updatedAt` timestamp:

```sh
python3 scripts/export_wiki_knowledge.py \
  --since 2026-08-01T00:00:00Z \
  --output data/wiki_export.jsonl
```

The exporter writes a temporary file and atomically replaces the destination after a successful export. Generated exports are ignored by Git. It does not generate chunks, embeddings, or vector data.

## Reverse proxy and HTTPS

A subdomain is cleaner than `/wiki/` because Wiki.js 2.x assumes it is hosted at an origin root in several routes and generated assets. No existing nginx file was present in this repository, so the provided file is optional and does not replace the current Flask proxy:

```sh
sudo cp infrastructure/wikijs/nginx/wiki-subdomain.conf.example /etc/nginx/sites-available/pimonitor-wiki
sudoedit /etc/nginx/sites-available/pimonitor-wiki
sudo ln -s /etc/nginx/sites-available/pimonitor-wiki /etc/nginx/sites-enabled/pimonitor-wiki
sudo nginx -t
sudo systemctl reload nginx
```

Replace the reserved `wiki.example.invalid` placeholder with a real hostname you control, point DNS at the server, then use the host's existing Certbot workflow to add TLS. Set Wiki.js's site URL and `WIKIJS_URL` to the resulting `https://...` origin. Keep the Compose bind address on loopback when nginx is on the host.

If no hostname exists yet, direct LAN/Tailscale access on `http://SERVER_IP:3000` is supported. Production access over the public internet should use HTTPS.

## Database backup

Backups use PostgreSQL's custom `pg_dump` format, are created with mode `0600`, and are stored under the Git-ignored `backups/wikijs/` directory by default:

```sh
make wiki-backup
```

Override the destination without changing the script:

```sh
WIKIJS_BACKUP_DIR=/mnt/secure-backups/wikijs make wiki-backup
```

Copy backups to another machine or encrypted backup target. A Docker volume is persistence, not a backup.

## Database restore

Restore is intentionally explicit and interactive. It stops Wiki.js to prevent concurrent writes, uses `pg_restore --clean --if-exists`, and restarts Wiki.js only after success:

```sh
make wiki-restore BACKUP=/absolute/path/to/wikijs-20260830T120000Z.dump
```

Type `RESTORE_WIKIJS` at the warning prompt. For an intentional non-interactive recovery:

```sh
WIKIJS_RESTORE_CONFIRM=RESTORE_WIKIJS \
  make wiki-restore BACKUP=/absolute/path/to/wikijs-backup.dump
```

If restore fails, Wiki.js remains stopped so the database can be inspected before a manual `make wiki-up`.

## Updating

The default image is pinned in `.env.example` for repeatability. Before changing it:

```sh
make wiki-backup
```

Review the [Wiki.js release notes](https://github.com/requarks/wiki/releases), change `WIKIJS_IMAGE` in the real `.env`, then:

```sh
make wiki-pull
make wiki-up
make wiki-status
make wiki-logs
```

Do not deploy the Wiki.js 3.x alpha image for this stack without also revisiting the GraphQL client and migration plan.

## Troubleshooting

- **Compose says `.env` is missing or the password is required:** copy `.env.example` and set the generated database password.
- **Database is unhealthy:** run `make wiki-logs`; confirm the same user, database, and password variables are used by both services.
- **Wiki.js is not reachable remotely:** the secure default binds only `127.0.0.1`; use a tunnel, reverse proxy, Tailscale IP, or an intentional bind-address change.
- **Flask link is absent:** set `WIKIJS_URL` in the Flask service environment and restart Flask.
- **Exporter says not configured:** both `WIKIJS_URL` and `WIKIJS_API_TOKEN` are required for extraction.
- **GraphQL returns forbidden:** verify API access, extraction-group permissions, locale, and page rules.
- **Healthcheck remains unhealthy during setup:** inspect `make wiki-logs`; the healthcheck allows a 60-second startup period before failures count.
