#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod.yml)
ACTION="${1:-up}"

require_env() {
  if [[ ! -f .env ]]; then
    echo "Нет .env. Скопируй .env.example → .env и заполни production-значения."
    exit 1
  fi
}

require_docker() {
  command -v docker >/dev/null || { echo "Нужен Docker"; exit 1; }
  docker compose version >/dev/null || { echo "Нужен Docker Compose"; exit 1; }
}

check_prod_secrets() {
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a

  if [[ "${ENVIRONMENT:-}" != "production" ]]; then
    echo "В .env для прода поставь ENVIRONMENT=production"
    exit 1
  fi

  if [[ -z "${SECRET_KEY:-}" || ${#SECRET_KEY} -lt 32 || "$SECRET_KEY" == change-me* ]]; then
    echo "SECRET_KEY должен быть случайным и ≥ 32 символов (не change-me...)"
    exit 1
  fi

  for var in DB_PASSWORD REDIS_PASSWORD RABBITMQ_DEFAULT_PASS; do
    val="${!var:-}"
    if [[ -z "$val" || "$val" == change-me* ]]; then
      echo "$var не должен оставаться change-me"
      exit 1
    fi
  done

  cert="${TLS_CERT_PATH:-./deploy/certs/fullchain.pem}"
  key="${TLS_KEY_PATH:-./deploy/certs/privkey.pem}"
  if [[ ! -f "$cert" || ! -f "$key" ]]; then
    echo "Нужны TLS-файлы:"
    echo "  $cert"
    echo "  $key"
    exit 1
  fi
}

wait_ready() {
  echo "Ждём postgres/redis/rabbitmq..."
  "${COMPOSE[@]}" up -d postgres redis rabbitmq
  "${COMPOSE[@]}" up -d --wait postgres redis rabbitmq
}

migrate() {
  echo "Собираем image для миграций..."
  "${COMPOSE[@]}" build migrate
  echo "Применяем миграции..."
  "${COMPOSE[@]}" --profile migrate run --rm migrate
}

up() {
  require_docker
  require_env
  check_prod_secrets
  wait_ready
  migrate
  echo "Собираем и поднимаем production-стек..."
  "${COMPOSE[@]}" up -d --build --remove-orphans backend worker beat frontend proxy
  echo
  echo "Готово. Снаружи — nginx на портах ${HTTP_PORT:-80}/${HTTPS_PORT:-443}."
  echo "  статус: $0 status"
  echo "  логи:   $0 logs"
}

down() {
  require_docker
  "${COMPOSE[@]}" down --remove-orphans
}

logs() {
  require_docker
  shift || true
  "${COMPOSE[@]}" logs -f --tail=200 "${@:-proxy backend frontend worker beat}"
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
    check_prod_secrets
    wait_ready
    migrate
    ;;
  *)
    echo "Использование: $0 {up|down|logs|status|migrate}"
    exit 1
    ;;
esac
