# Staging deployment over SSH

This staging setup is intended for an HTTP-only server reachable by IP inside a trusted network.
It runs PostgreSQL, Django through Gunicorn, and Nginx through Docker Compose.

## 1. Server prerequisites

- Linux server with Docker Engine and the Docker Compose plugin.
- SSH access to the server.
- GitHub access from the server, using an SSH deploy key or another approved credential.
- TCP port `80` reachable only from the testing network.

If UFW is enabled, allow the real testing subnet rather than opening port 80 globally. Example:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 80 proto tcp
```

## 2. Clone the repository

```bash
ssh deploy@192.168.1.50
git clone git@github.com:alma-iceee/platform.git
cd platform
```

For an existing checkout:

```bash
git pull --ff-only origin main
```

## 3. Create the private environment file

```bash
cp .env.staging.example .env.staging
chmod 600 .env.staging
```

Generate secrets on the server:

```bash
openssl rand -base64 48
openssl rand -base64 32
```

Edit `.env.staging` and replace at least:

- `DJANGO_SECRET_KEY` with the first generated value;
- `POSTGRES_PASSWORD` with the second generated value;
- every `192.168.1.50` occurrence with the server's actual IP;
- `STAGING_BIND_ADDRESS` with the server IP when the service must listen only on that interface.

Keep these settings disabled while staging uses plain HTTP:

```env
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
```

`LOAD_DEMO_DATA=true` seeds demo data only when `admin@ordo.local` does not exist. Subsequent deploys do not rerun seed commands or reset demo passwords.

The built-in public demo dataset is used by default. To use the private organization seed, run the following from your workstation before the first start, without committing the file:

```bash
ssh deploy@192.168.1.50 'mkdir -p ~/platform/local_data && chmod 700 ~/platform/local_data'
scp local_data/private_seed_organization.json deploy@192.168.1.50:~/platform/local_data/
ssh deploy@192.168.1.50 'chmod 600 ~/platform/local_data/private_seed_organization.json'
```

Only the one-shot `init` container mounts this directory, read-only. It runs as container root so it can read the private file without weakening its server permissions; the long-running web container remains unprivileged.

## 4. Validate and start

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml config --quiet
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build --remove-orphans
docker compose --env-file .env.staging -f docker-compose.staging.yml ps
```

The `init` container runs migrations and `collectstatic`, then exits successfully. `web` starts only after `init` succeeds, and Nginx starts only after the Django healthcheck succeeds.

Verify from the server and from a tester's computer:

```bash
curl http://192.168.1.50/health/
```

Expected response:

```json
{"status": "ok"}
```

The application is available at `http://192.168.1.50/`. With demo seed enabled, the administrative demo account is `admin@ordo.local` / `admin`; do not expose this HTTP staging instance outside the trusted network.

## 5. Deploy an update

After changes are pushed to `main`:

```bash
ssh deploy@192.168.1.50
cd platform
git pull --ff-only origin main
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build --remove-orphans
docker compose --env-file .env.staging -f docker-compose.staging.yml ps
```

Migrations and static collection run automatically. PostgreSQL and uploaded media stay in named volumes.

## 6. Logs and checks

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml logs -f --tail=200
docker compose --env-file .env.staging -f docker-compose.staging.yml exec web python manage.py check --deploy --settings=config.settings.staging
```

The deployment check reports HTTPS/HSTS/secure-cookie warnings while this internal staging intentionally uses plain HTTP. They become mandatory fixes if the service is exposed outside the trusted network or moved to HTTPS.

Stop containers without deleting data:

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml down
```

Never add `--volumes` unless the staging database and uploaded media should be permanently deleted.

## 7. PostgreSQL backup

```bash
mkdir -p backups
docker compose --env-file .env.staging -f docker-compose.staging.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "backups/ordo-staging-$(date +%F-%H%M).sql.gz"
```

Copy backups away from the staging server on a regular schedule. Uploaded media in the `media_staging_data` volume needs a separate filesystem backup if testers attach important files.
