# GitHub Actions

Two workflows are provided:

- **CI** runs automatically for pushes to `main` and pull requests. It executes the knowledge tests, compiles Python and Jinja templates, validates the shell scripts, and validates the Wiki.js Compose model with a non-secret test password.
- **Deploy production** is intentionally manual (`workflow_dispatch`). It connects to the server, performs a fast-forward-only update, starts/updates Wiki.js, restarts the existing Flask systemd service, and checks both HTTP endpoints.

The deployment workflow does not contain a hostname, username, private key, password, or host key. Configure these in **GitHub → Settings → Secrets and variables → Actions**, preferably in the protected `production` environment:

| Secret | Value |
| --- | --- |
| `DEPLOY_HOST` | Server hostname or Tailscale IP reachable from the selected runner |
| `DEPLOY_USER` | SSH user owning `~/Desktop/Enhanced-Pi-Monitor` |
| `DEPLOY_PORT` | SSH port; optional, defaults to `22` |
| `DEPLOY_SSH_PRIVATE_KEY` | Dedicated deployment private key, without a passphrase |
| `DEPLOY_KNOWN_HOSTS` | Verified `known_hosts` entry for the exact host and port |

Use a dedicated deploy key rather than a personal everyday key. Add its public half to the server user's `~/.ssh/authorized_keys` and restrict it according to the server's operational needs. Never upload `sshKey.txt`, `.env`, or a private key to the repository.

Before enabling the workflow, verify on the server that:

```sh
cd ~/Desktop/Enhanced-Pi-Monitor
git fetch origin main
docker compose version
sudo -n systemctl status pimonitor.service
test -f infrastructure/wikijs/.env
```

The server must already have its real Wiki.js database password in `infrastructure/wikijs/.env`; GitHub does not receive that password. The server also needs credentials to fetch this GitHub repository.

Run **Actions → Deploy production → Run workflow** only after CI has passed. Configure production-environment approvals in GitHub if deployment should require an explicit reviewer.
