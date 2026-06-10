COMPOSE=docker compose -f docker-compose.dev.yml
WEB=$(COMPOSE) run --rm web

up:
	$(COMPOSE) up --build

up-d:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

check:
	$(WEB) python manage.py check

migrate:
	$(WEB) python manage.py migrate

makemigrations:
	$(WEB) python manage.py makemigrations

test:
	$(WEB) python manage.py test

shell:
	$(WEB) python manage.py shell

bash:
	$(WEB) bash

createsuperuser:
	$(WEB) python manage.py createsuperuser

clean-pyc:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
