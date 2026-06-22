export COMPOSE_FILE := "docker-compose.yml"

HTMX_VERSION := "2.0.8"

default:
  @just --list

# Setup: install deps, build container, fresh db, initial user
setup:
  uv sync
  if [ ! -f .env ]; then cp .env.local.example .env; fi
  docker compose down -v
  docker compose build
  docker compose run --rm django python manage.py migrate
  docker compose run --rm django python manage.py loaddata seed_apps
  docker compose run --rm django python manage.py ensure_initial_user
  docker compose run --rm django python manage.py seed_demo_data
  docker compose run --rm django python manage.py createsuperuser --noinput || true

# Start containers (Postgres + Django dev server)
up:
  docker compose up

# Stop containers
down:
  docker compose down

# Run a manage.py command in the container
manage *args="--help":
  docker compose run --rm django python manage.py {{args}}

# Run Django tests
test:
  docker compose run --rm django uv run pytest

# Lint + format
lint:
  uv run ruff check .
  uv run ruff format --check .

format:
  uv run ruff check --fix .
  uv run ruff format .

# Haal een client-credentials access_token van de profielservice OAuth-server
m2m-token client_id="wies-m2m" client_secret="local-dev-secret-wies":
  @curl -s -X POST http://localhost:8000/o/token/ \
    -d grant_type=client_credentials \
    -d scope=read_profile \
    -d client_id={{client_id}} \
    -d client_secret={{client_secret}} | jq -r .access_token

# Demo-flow: start met SKIP_OIDC=false zodat SSO-login via Wies-dev realm loopt
demo-sso:
  SKIP_OIDC=false docker compose up

# Download vendored frontend libs
update-vendor:
  @echo "Downloading vendor packages..."
  @mkdir -p rijksprofielservice/core/static/vendor/htmx
  curl -sL "https://unpkg.com/htmx.org@{{HTMX_VERSION}}/dist/htmx.min.js" \
    -o rijksprofielservice/core/static/vendor/htmx/htmx.min.js
  @echo "Done: htmx.min.js ({{HTMX_VERSION}})"
