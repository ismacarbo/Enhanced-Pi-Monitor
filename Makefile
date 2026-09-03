WIKI_DIR := infrastructure/wikijs
WIKI_ENV := $(WIKI_DIR)/.env
WIKI_COMPOSE := docker compose --project-directory $(WIKI_DIR) --env-file $(WIKI_ENV) -f $(WIKI_DIR)/docker-compose.yml

.PHONY: deploy-pi wiki-check-env wiki-up wiki-down wiki-logs wiki-restart wiki-status wiki-pull wiki-backup wiki-restore

deploy-pi:
	./scripts/deploy_pi.sh

wiki-check-env:
	@test -f $(WIKI_ENV) || (echo "Missing $(WIKI_ENV). Copy $(WIKI_DIR)/.env.example first." >&2; exit 2)

wiki-up: wiki-check-env
	$(WIKI_COMPOSE) up -d

wiki-down: wiki-check-env
	$(WIKI_COMPOSE) down

wiki-logs: wiki-check-env
	$(WIKI_COMPOSE) logs -f --tail=200

wiki-restart: wiki-check-env
	$(WIKI_COMPOSE) restart wikijs

wiki-status: wiki-check-env
	$(WIKI_COMPOSE) ps

wiki-pull: wiki-check-env
	$(WIKI_COMPOSE) pull

wiki-backup: wiki-check-env
	$(WIKI_DIR)/scripts/backup.sh

wiki-restore: wiki-check-env
	@test -n "$(BACKUP)" || (echo "Usage: make wiki-restore BACKUP=/path/to/wikijs.dump" >&2; exit 2)
	$(WIKI_DIR)/scripts/restore.sh "$(BACKUP)"
