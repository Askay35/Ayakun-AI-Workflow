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

wait_ready() {
  echo "Ждём postgres/redis/rabbitmq..."
  "${COMPOSE[@]}" up -d postgres redis rabbitmq
  "${COMPOSE[@]}" up -d --wait postgres redis rabbitmq
}

migrate() {
  echo "Применяем миграции..."
  "${COMPOSE[@]}" --profile migrate run --rm migrate
}

up() {
  require_docker
  require_env
  wait_ready
  migrate
  echo "Поднимаем backend, worker, beat, frontend..."
  "${COMPOSE[@]}" up -d --build backend worker beat frontend
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
    wait_ready
    migrate
    ;;
  *)
    echo "Использование: $0 {up|down|logs|status|migrate}"
    exit 1
    ;;
esac
