#!/usr/bin/env bash
# Healthcheck for the train tickets bot.
# Runs from systemd timer, checks the container, recent Telegram polling and
# pass.rw.by reachability, and messages ALERT_CHAT_ID when the state changes.

set -u

ENV_FILE="${ENV_FILE:-/root/train-tickets-tgbot/.env}"
STATE_DIR="${STATE_DIR:-/var/lib/tgbot-health}"
STATE_FILE="${STATE_DIR}/state"

mkdir -p "${STATE_DIR}"

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

TELEGRAM_API_HOST="${TELEGRAM_API_IP:-149.154.167.220}"
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

send_message() {
    [ -n "${BOT_TOKEN:-}" ] && [ -n "${ALERT_CHAT_ID:-}" ] || return 0

    if curl -sS -m 15 --resolve "api.telegram.org:443:${TELEGRAM_API_HOST}" \
        --data-urlencode "chat_id=${ALERT_CHAT_ID}" \
        --data-urlencode "text=$1" \
        "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" >/dev/null 2>&1; then
        echo "alert sent: $1"
    else
        echo "alert failed: $1"
    fi
}

container_ok=0
if docker inspect -f '{{.State.Running}}' tickets-app 2>/dev/null | grep -q true; then
    container_ok=1
fi

polling_ok=0
if docker logs --since 15m tickets-app 2>&1 | grep -q 'getUpdates succeeded'; then
    polling_ok=1
fi

rw_ok=0
if curl -fsS -m 10 -A "${USER_AGENT}" -o /dev/null https://pass.rw.by/ru/ 2>/dev/null; then
    rw_ok=1
fi

current="container=${container_ok} polling=${polling_ok} rw=${rw_ok}"
previous=$(cat "${STATE_FILE}" 2>/dev/null || echo unknown)

if [ "${current}" != "${previous}" ]; then
    if [ "${container_ok}" -eq 1 ] && [ "${polling_ok}" -eq 1 ] && [ "${rw_ok}" -eq 1 ]; then
        send_message "✅ Бот в норме: контейнер работает, Telegram опрашивается, pass.rw.by доступен."
    else
        send_message "⚠️ Проблема с ботом: ${current}. Логи: docker logs --tail 50 tickets-app"
    fi

    printf '%s\n' "${current}" > "${STATE_FILE}"
fi

if [ -n "${HEALTHCHECK_URL:-}" ]; then
    if [ "${container_ok}${polling_ok}${rw_ok}" = "111" ]; then
        curl -fsS -m 10 -o /dev/null "${HEALTHCHECK_URL}" || true
    else
        curl -fsS -m 10 -o /dev/null "${HEALTHCHECK_URL%/}/fail" || true
    fi
fi
