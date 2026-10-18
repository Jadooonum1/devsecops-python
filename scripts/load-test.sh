#!/usr/bin/env bash
# Drive enough traffic through the Ingress to make the backend HPA scale out,
# while sampling `kubectl get hpa` so the scale-out/in can be shown afterwards.
#
#   WORKERS=16 DURATION=240 ./scripts/load-test.sh
set -uo pipefail
HOST=${HOST:-shelflend.local}
URL=${URL:-http://127.0.0.1}
NS=${NS:-shelflend}
WORKERS=${WORKERS:-16}
DURATION=${DURATION:-240}
COOLDOWN=${COOLDOWN:-150}
OUT=${OUT:-load-test-hpa.txt}

paths=(/api/books /api/stats /api/loans?status=active /api/members /api/books?q=dev /api/activity)

worker() {
  local end=$((SECONDS + DURATION)) i=0
  while ((SECONDS < end)); do
    curl -s -o /dev/null -H "Host: $HOST" "$URL${paths[i % ${#paths[@]}]}"
    # a few deliberate conflicts so the 4xx series is not empty
    ((i % 25 == 0)) && curl -s -o /dev/null -H "Host: $HOST" -H 'content-type: application/json' \
      -d '{"isbn":"9780134685991","title":"dup","author":"x"}' "$URL/api/books"
    i=$((i + 1))
  done
}

echo "load: $WORKERS workers x ${DURATION}s against $URL (Host: $HOST)" | tee "$OUT"
for _ in $(seq "$WORKERS"); do worker & done
start=$SECONDS
while ((SECONDS - start < DURATION + COOLDOWN)); do
  printf '%4ds  %s\n' $((SECONDS - start)) \
    "$(kubectl -n "$NS" get hpa shelflend-backend --no-headers -o custom-columns=CPU:.status.currentMetrics[0].resource.current.averageUtilization,DESIRED:.status.desiredReplicas,CURRENT:.status.currentReplicas | awk '{print "cpu="$1"%  desired="$2"  current="$3}')" | tee -a "$OUT"
  sleep 15
done
wait
echo "done" | tee -a "$OUT"
