#!/usr/bin/env bash
# Rule 7 verification: assert that no meal photo can survive on disk.
# Checks Nginx temp directories, container /tmp mounts, swap and log contents.
# Run by `make check-ephemeral`, and as the last step of `make deploy`.
set -uo pipefail

FAIL=0
pass() { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }

echo "== 1. host swap =="
if [[ "$(swapon --noheadings 2>/dev/null | wc -l)" -eq 0 ]]; then
    pass "no swap device active"
else
    fail "swap is active -- a decoded image could be paged out; run: sudo swapoff -a"
fi

echo "== 2. nginx temp directories empty =="
if docker compose exec -T nginx sh -c 'ls -A /var/cache/nginx/client_temp 2>/dev/null | wc -l' \
     | tr -d "\r" | grep -qx 0; then
    pass "client_temp is empty"
else
    fail "client_temp is not empty -- a request body was spooled to disk"
fi

echo "== 3. container /tmp is tmpfs =="
for svc in nginx backend llm; do
    if docker compose exec -T "$svc" sh -c 'df -T /tmp 2>/dev/null || mount' \
         | grep -qi tmpfs; then
        pass "$svc: /tmp on tmpfs"
    else
        fail "$svc: /tmp is not tmpfs"
    fi
done

echo "== 4. container swap disabled =="
for svc in backend llm; do
    if docker compose exec -T "$svc" sh -c 'cat /proc/meminfo | grep ^SwapTotal' \
         | grep -qE 'SwapTotal: +0 kB'; then
        pass "$svc: no swap"
    else
        fail "$svc: swap is visible inside the container"
    fi
done

echo "== 5. no image bytes in logs =="
if docker compose logs --no-color --tail 2000 2>/dev/null | grep -qi 'JFIF\|\\xff\\xd8'; then
    fail "JPEG magic bytes found in logs -- a request body is being logged"
else
    pass "no JPEG data in recent logs"
fi

echo "== 6. no image column in the schema =="
if docker compose exec -T postgres sh -c \
     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from information_schema.columns where column_name ~ '"'"'(image|photo)_?(data|bytes|blob|path)'"'"'"' \
     2>/dev/null | tr -d "\r" | grep -qx 0; then
    pass "no image-bearing column exists"
else
    fail "the schema has a column that could hold an image"
fi

echo
if [[ $FAIL -eq 0 ]]; then
    echo "Rule 7 holds."
else
    echo "Rule 7 is BROKEN -- see docs/ephemeral-processing.md. Do not enrol participants." >&2
fi
exit $FAIL
