#!/usr/bin/env bash
# Healthcheck for the train tickets bot.
# Runs from systemd timer, checks the container, recent Telegram polling and
# pass.rw.by reachability, and messages ALERT_CHAT_ID when the state changes.

set -u

ENV_FILE="${ENV_FILE:-/root/train-tickets-tgbot/.env}"
STATE_DIR="${STATE_DIR:-/var/lib/tgbot-health}"
STATE_FILE="${STATE_DIR}/state"
LAST_RW_OK_FILE="${STATE_DIR}/last_rw_ok"

mkdir -p "${STATE_DIR}"

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

TELEGRAM_API_HOST="${TELEGRAM_API_IP:-149.154.167.220}"
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
RW_CHECK_URL="${RW_CHECK_URL:-https://pass.rw.by/ru/}"

send_message() {
    if [ "${DRY_RUN:-0}" = "1" ]; then
        printf 'would send: %s\n' "$1"
        return 0
    fi

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

container_state=$(docker inspect -f '{{.State.Status}}' tickets-app 2>/dev/null || echo missing)
container_ok=0
[ "${container_state}" = "running" ] && container_ok=1

polling_ok=0
if docker logs --since 15m tickets-app 2>&1 | grep -q 'getUpdates succeeded'; then
    polling_ok=1
fi

rw_ok=1
rw_code="skip"
active_count=$(docker exec -i tickets-postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
    "select count(*) from ticket_requests where is_active=true" 2>/dev/null | tr -d '[:space:]')
case "${active_count}" in
    ''|*[!0-9]*) active_count=0 ;;
esac

if [ "${active_count}" -gt 0 ]; then
    rw_result=$(curl -sS -m 10 -A "${USER_AGENT}" -o /dev/null -w '%{http_code} %{time_total}' "${RW_CHECK_URL}" 2>/dev/null || true)
    rw_code="${rw_result%% *}"
    rw_time="${rw_result##* }"
    [ -z "${rw_code}" ] && rw_code=000

    rw_ok=0
    case "${rw_code}" in
        2*|3*) rw_ok=1 ;;
    esac
fi

case "${rw_code}" in
    skip) rw_desc="пропущено — нет активных поисков" ;;
    000) rw_desc="нет ответа за 10 с, похоже на блок WAF" ;;
    403) rw_desc="HTTP 403 Access denied (WAF сайта)" ;;
    2*|3*) rw_desc="HTTP ${rw_code} за ${rw_time} с" ;;
    *) rw_desc="HTTP ${rw_code}" ;;
esac

last_ok_local="неизвестно"
if [ -s "${LAST_RW_OK_FILE}" ]; then
    last_ok_local=$(date -d "@$(cat "${LAST_RW_OK_FILE}")" '+%H:%M' 2>/dev/null || echo "неизвестно")
fi

if [ "${rw_ok}" -eq 1 ] && [ "${rw_code}" != "skip" ]; then
    date +%s > "${LAST_RW_OK_FILE}"
fi

current="container=${container_ok} polling=${polling_ok} rw=${rw_ok}"
previous=$(cat "${STATE_FILE}" 2>/dev/null || echo unknown)

if [ "${current}" != "${previous}" ]; then
    if [ "${container_ok}" -eq 1 ] && [ "${polling_ok}" -eq 1 ] && [ "${rw_ok}" -eq 1 ]; then
        message=$(printf '✅ Бот в норме\n• контейнер: работает\n• Telegram: опрашивается\n• pass.rw.by: %s (последняя проверка %s)' "${rw_desc}" "${last_ok_local}")
    else
        problems=""
        if [ "${container_ok}" -eq 0 ]; then
            problems="${problems}
• контейнер: ${container_state}"
        else
            problems="${problems}
• контейнер: работает"
        fi

        if [ "${polling_ok}" -eq 0 ]; then
            problems="${problems}
• Telegram: нет успешных опросов за 15 мин"
        else
            problems="${problems}
• Telegram: опрашивается"
        fi

        if [ "${rw_ok}" -eq 0 ]; then
            problems="${problems}
• pass.rw.by: ${rw_desc} (последняя успешная проверка ${last_ok_local})"
        else
            problems="${problems}
• pass.rw.by: ${rw_desc}"
        fi

        message=$(printf '⚠️ Проблема с ботом:%s' "${problems}")
    fi

    send_message "${message}"
    printf '%s\n' "${current}" > "${STATE_FILE}"
fi

if [ -n "${HEALTHCHECK_URL:-}" ]; then
    if [ "${container_ok}${polling_ok}${rw_ok}" = "111" ]; then
        curl -fsS -m 10 -o /dev/null "${HEALTHCHECK_URL}" || true
    else
        curl -fsS -m 10 -o /dev/null "${HEALTHCHECK_URL%/}/fail" || true
    fi
fi
