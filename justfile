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

# Download vendored frontend libs
update-vendor:
  @echo "Downloading vendor packages..."
  @mkdir -p rijksprofielservice/core/static/vendor/htmx
  curl -sL "https://unpkg.com/htmx.org@{{HTMX_VERSION}}/dist/htmx.min.js" \
    -o rijksprofielservice/core/static/vendor/htmx/htmx.min.js
  @echo "Done: htmx.min.js ({{HTMX_VERSION}})"
