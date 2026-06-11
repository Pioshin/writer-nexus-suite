#!/usr/bin/env bash
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────
FRONTEND_DIR="/home/pioshin/AI/Projects/P_NOOS/Writers_Nexus/WN_Frontend"
NOOS_DIR="/home/pioshin/AI/Projects/P_NOOS/Writers_Nexus/NOOS"
VENV="/home/pioshin/.venv/workspace"

# ── Ports ──────────────────────────────────────────────────────
FE_PORT="55099"       # live-server  (frontend)
BE_PORT="9090"        # uvicorn      (NOOS Hub backend)

FE_URL="http://127.0.0.1:${FE_PORT}"
BE_URL="http://127.0.0.1:${BE_PORT}"

FE_LOG="${FRONTEND_DIR}/.writers-nexus-frontend.log"
BE_LOG="${NOOS_DIR}/.writers-nexus-backend.log"

# ── Helpers ────────────────────────────────────────────────────

port_listening() {
  ss -ltn "( sport = :$1 )" 2>/dev/null | grep -q ":$1"
}

notify() {
  local msg="$1"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Writers Nexus" "$msg"
  fi
  echo "$msg"
}

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    kill ${pids} 2>/dev/null || true
    sleep 1
  fi
  # Force-kill if still alive
  if port_listening "${port}"; then
    pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
      kill -9 ${pids} 2>/dev/null || true
      sleep 1
    fi
  fi
}

# ── Stop ───────────────────────────────────────────────────────

stop_all() {
  kill_port "${BE_PORT}"
  kill_port "${FE_PORT}"

  local ok=true
  if port_listening "${BE_PORT}"; then
    notify "Non riesco a fermare il backend (porta ${BE_PORT})."
    ok=false
  fi
  if port_listening "${FE_PORT}"; then
    notify "Non riesco a fermare il frontend (porta ${FE_PORT})."
    ok=false
  fi
  if $ok; then
    notify "Writers Nexus arrestato (frontend :${FE_PORT}, backend :${BE_PORT})."
  fi
}

# ── Start ──────────────────────────────────────────────────────

start_all() {
  # 1) Start NOOS Hub backend (uvicorn)
  if port_listening "${BE_PORT}"; then
    echo "Backend già attivo su :${BE_PORT}, skip."
  else
    cd "${NOOS_DIR}"
    "${VENV}/bin/uvicorn" noos.main:app \
      --host 127.0.0.1 --port "${BE_PORT}" \
      >>"${BE_LOG}" 2>&1 &
    disown
    # Wait for backend to be ready (max 10 s)
    local tries=0
    while ! port_listening "${BE_PORT}" && (( tries < 20 )); do
      sleep 0.5
      (( tries++ )) || true
    done
    if port_listening "${BE_PORT}"; then
      echo "Backend NOOS avviato su ${BE_URL}"
    else
      notify "Avvio backend fallito. Controlla: ${BE_LOG}"
      exit 1
    fi
  fi

  # 2) Start frontend (live-server)
  if port_listening "${FE_PORT}"; then
    echo "Frontend già attivo su :${FE_PORT}, skip."
  else
    cd "${FRONTEND_DIR}"
    npx live-server --host=127.0.0.1 --port="${FE_PORT}" \
      >>"${FE_LOG}" 2>&1 &
    disown
    local fe_tries=0
    while ! port_listening "${FE_PORT}" && (( fe_tries < 10 )); do
      sleep 0.5
      (( fe_tries++ )) || true
    done
    if port_listening "${FE_PORT}"; then
      echo "Frontend avviato su ${FE_URL}"
    else
      notify "Avvio frontend fallito. Controlla: ${FE_LOG}"
      exit 1
    fi
  fi

  notify "Writers Nexus avviato ✓  Frontend: ${FE_URL}  Backend: ${BE_URL}"
  xdg-open "${FE_URL}" >/dev/null 2>&1 &
  disown
}

# ── Toggle ─────────────────────────────────────────────────────

if port_listening "${FE_PORT}" || port_listening "${BE_PORT}"; then
  stop_all
else
  start_all
fi
