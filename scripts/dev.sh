#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose --env-file .env -f docker-compose.yml)
ACTION="${1:-up}"

require_env() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Создан .env из .env.example — заполни пароли и ключи, затем запусти снова."
    exit 1
  fi
}

require_docker() {
  command -v docker >/dev/null || { echo "Нужен Docker"; exit 1; }
  docker compose version >/dev/null || { echo "Нужен Docker Compose"; exit 1; }
}

check_docker_urls() {
  local db_url redis_url broker
  db_url="$(grep -E '^DB_URL=' .env | tail -1 | cut -d= -f2- || true)"
  redis_url="$(grep -E '^REDIS_URL=' .env | tail -1 | cut -d= -f2- || true)"
  broker="$(grep -E '^CELERY_BROKER_URL=' .env | tail -1 | cut -d= -f2- || true)"

  if [[ -z "$db_url" || "$db_url" == *"@localhost"* ]]; then
    echo "DB_URL должен указывать на хост postgres (не localhost), например:"
    echo "  DB_URL=postgresql+asyncpg://USER:PASS@postgres:5432/yakun"
    exit 1
  fi
  if [[ -z "$redis_url" || "$redis_url" == *"@localhost"* ]]; then
    echo "REDIS_URL должен указывать на хост redis (не localhost)."
    exit 1
  fi
  if [[ -z "$broker" || "$broker" == *"@localhost"* ]]; then
    echo "CELERY_BROKER_URL должен указывать на rabbitmq, например:"
    echo "  CELERY_BROKER_URL=amqp://USER:PASS@rabbitmq:5672/yakun"
    exit 1
  fi
}

wait_ready() {
  echo "Ждём postgres/redis/rabbitmq..."
  "${COMPOSE[@]}" up -d --remove-orphans postgres redis rabbitmq
  "${COMPOSE[@]}" up -d --wait postgres redis rabbitmq
}

migrate() {
  echo "Применяем миграции..."
  "${COMPOSE[@]}" --profile migrate run --rm migrate
}

up() {
  require_docker
  require_env
  check_docker_urls
  wait_ready
  migrate
  echo "Поднимаем backend, worker, beat, frontend..."
  "${COMPOSE[@]}" up -d --build --remove-orphans backend worker beat frontend
  # shellcheck disable=SC1091
  set -a; source .env; set +a
  echo
  echo "Готово:"
  echo "  сайт:  http://localhost:${FRONTEND_PORT:-3000}"
  echo "  API:   http://localhost:${BACKEND_PORT:-8000}/docs"
  echo "  логи:  $0 logs"
}

down() {
  require_docker
  "${COMPOSE[@]}" down --remove-orphans
}

logs() {
  require_docker
  shift || true
  "${COMPOSE[@]}" logs -f --tail=200 "${@:-backend frontend worker beat}"
}

status() {
  require_docker
  "${COMPOSE[@]}" ps
}

case "$ACTION" in
  up) up ;;
  down) down ;;
  logs) logs "$@" ;;
  status|ps) status ;;
  migrate)
    require_docker
    require_env
    check_docker_urls
    wait_ready
    migrate
    ;;
  *)
    echo "Использование: $0 {up|down|logs|status|migrate}"
    exit 1
    ;;
esac
