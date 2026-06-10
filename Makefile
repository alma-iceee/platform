COMPOSE_DEV=docker compose -f docker-compose.dev.yml
COMPOSE_STAGING=docker compose -f docker-compose.staging.yml
COMPOSE_PROD=docker compose -f docker-compose.prod.yml

WEB_DEV=$(COMPOSE_DEV) run --rm web
WEB_STAGING=$(COMPOSE_STAGING) run --rm web
WEB_PROD=$(COMPOSE_PROD) run --rm web

DEV_SETTINGS=config.settings.dev
STAGING_SETTINGS=config.settings.staging
PROD_SETTINGS=config.settings.prod
CI_SETTINGS=config.settings.ci


# DEV

up:
	$(COMPOSE_DEV) up --build

up-d:
	$(COMPOSE_DEV) up -d --build

down:
	$(COMPOSE_DEV) down

restart:
	$(COMPOSE_DEV) restart web

rebuild-web:
	$(COMPOSE_DEV) up -d --build web

logs:
	$(COMPOSE_DEV) logs -f

check:
	$(WEB_DEV) python manage.py check --settings=$(DEV_SETTINGS)

migrate:
	$(WEB_DEV) python manage.py migrate --settings=$(DEV_SETTINGS)

makemigrations:
	$(WEB_DEV) python manage.py makemigrations --settings=$(DEV_SETTINGS)

test:
	$(WEB_DEV) python manage.py test --settings=$(CI_SETTINGS)

shell:
	$(WEB_DEV) python manage.py shell --settings=$(DEV_SETTINGS)

bash:
	$(WEB_DEV) bash

createsuperuser:
	$(WEB_DEV) python manage.py createsuperuser --settings=$(DEV_SETTINGS)


# STAGING

staging-up:
	$(COMPOSE_STAGING) up -d --build

staging-down:
	$(COMPOSE_STAGING) down

staging-logs:
	$(COMPOSE_STAGING) logs -f

staging-check:
	$(WEB_STAGING) python manage.py check --settings=$(STAGING_SETTINGS)

staging-migrate:
	$(WEB_STAGING) python manage.py migrate --settings=$(STAGING_SETTINGS)


# PROD

prod-up:
	$(COMPOSE_PROD) up -d --build

prod-down:
	$(COMPOSE_PROD) down

prod-logs:
	$(COMPOSE_PROD) logs -f

prod-check:
	$(WEB_PROD) python manage.py check --settings=$(PROD_SETTINGS)

prod-migrate:
	$(WEB_PROD) python manage.py migrate --settings=$(PROD_SETTINGS)


# CLEAN

clean-pyc:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +