import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
    scenarios: {
        analyze_smoke: {
            executor: "ramping-vus",
            startVUs: 1,
            stages: [
                { duration: "30s", target: 5 },
                { duration: "1m", target: 15 },
                { duration: "30s", target: 0 },
            ],
        },
    },
    thresholds: {
        http_req_failed: ["rate<0.02"],
        http_req_duration: ["p(95)<5000", "p(99)<12000"],
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const TOKEN = __ENV.BEARER_TOKEN || "";

const payload = JSON.stringify({
    text: "Client VIC cherche un cadeau anniversaire, budget 5000 euros, prefere cuir noir.",
    language: "FR",
});

const headers = {
    "Content-Type": "application/json",
};

if (TOKEN) {
    headers.Authorization = `Bearer ${TOKEN}`;
}

export default function () {
    const res = http.post(`${BASE_URL}/api/analyze`, payload, { headers });
    check(res, {
        "status is 200": (r) => r.status === 200,
        "has tags": (r) => {
            if (r.status !== 200) return false;
            const body = r.json();
            return Array.isArray(body.tags);
        },
    });
    sleep(1);
}
