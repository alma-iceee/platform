#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

if [ "${LOAD_DEMO_DATA:-false}" = "true" ]; then
    if python manage.py shell -c "from django.contrib.auth import get_user_model; raise SystemExit(0 if get_user_model().objects.filter(email='admin@ordo.local').exists() else 1)"; then
        echo "Demo data already exists; skipping seed commands."
    else
        python manage.py seed_organization_demo
        python manage.py seed_workspace_demo
        python manage.py seed_task_demo
    fi
fi
