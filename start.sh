#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly BACKEND_DIR="${ROOT_DIR}/backend"
readonly FRONTEND_DIR="${ROOT_DIR}/frontend"
readonly COMPOSE_FILE="${BACKEND_DIR}/compose.yaml"

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: ./start.sh [--check]

Starts PostgreSQL and FastAPI with Docker Compose and the Next.js frontend in development mode.
  --check  validates prerequisites without starting the services
EOF
  exit 0
fi

if [[ -n "${1:-}" && "${1}" != "--check" ]]; then
  printf 'Unknown argument: %s\nRun ./start.sh --help to view the available options.\n' "$1" >&2
  exit 2
fi

for required_command in docker npm; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "${required_command}" >&2
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  printf 'Docker is unavailable. Start the Docker daemon and try again.\n' >&2
  exit 1
fi

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  printf 'Missing file: backend/.env\nCopy backend/.env.example and configure OPENAI_API_KEY.\n' >&2
  exit 1
fi

if [[ ! -f "${FRONTEND_DIR}/.env" ]]; then
  printf 'Missing file: frontend/.env\nCopy frontend/.env.example before starting.\n' >&2
  exit 1
fi

docker compose \
  --env-file "${BACKEND_DIR}/.env" \
  -f "${COMPOSE_FILE}" \
  config --quiet

if [[ "${1:-}" == "--check" ]]; then
  printf 'Prerequisites are valid. Backend: :8000 | Frontend: :3000\n'
  exit 0
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  printf 'Installing frontend dependencies...\n'
  npm --prefix "${FRONTEND_DIR}" install
fi

backend_pid=""
frontend_pid=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  printf '\nStopping frontend and backend...\n'

  if [[ -n "${frontend_pid}" ]] && kill -0 "${frontend_pid}" 2>/dev/null; then
    kill -TERM "${frontend_pid}" 2>/dev/null || true
  fi
  if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill -TERM "${backend_pid}" 2>/dev/null || true
  fi

  [[ -z "${frontend_pid}" ]] || wait "${frontend_pid}" 2>/dev/null || true
  [[ -z "${backend_pid}" ]] || wait "${backend_pid}" 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

printf 'Starting EnterOS...\n'
printf 'Frontend: http://localhost:3000\n'
printf 'API:      http://localhost:8000\n'
printf 'Swagger:  http://localhost:8000/docs\n\n'

docker compose \
  --env-file "${BACKEND_DIR}/.env" \
  -f "${COMPOSE_FILE}" \
  up --build &
backend_pid=$!

npm --prefix "${FRONTEND_DIR}" run dev &
frontend_pid=$!

wait -n "${backend_pid}" "${frontend_pid}"
