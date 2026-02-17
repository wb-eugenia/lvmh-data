const trimTrailingSlash = (value) => (value || "").replace(/\/+$/, "");

const API_BASE = trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || "");
const WS_BASE = trimTrailingSlash(import.meta.env.VITE_WS_BASE_URL || "");

export const apiUrl = (path) => {
    if (!path) return API_BASE || "";
    if (/^https?:\/\//i.test(path)) return path;

    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return API_BASE ? `${API_BASE}${normalizedPath}` : normalizedPath;
};

const deriveWsBaseFromApi = () => {
    if (!API_BASE) return "";
    if (API_BASE.startsWith("https://")) return `wss://${API_BASE.slice("https://".length)}`;
    if (API_BASE.startsWith("http://")) return `ws://${API_BASE.slice("http://".length)}`;
    return "";
};

export const wsUrl = (path) => {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    if (WS_BASE) return `${WS_BASE}${normalizedPath}`;

    const derived = deriveWsBaseFromApi();
    if (derived) return `${derived}${normalizedPath}`;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${normalizedPath}`;
};

const buildHeadersWithAuth = (headers) => {
    const token = localStorage.getItem("token");
    if (!token) return headers;

    if (headers instanceof Headers) {
        if (!headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${token}`);
        }
        return headers;
    }

    const merged = { ...(headers || {}) };
    const hasAuthorization = Object.keys(merged).some((key) => key.toLowerCase() === "authorization");
    if (!hasAuthorization) {
        merged.Authorization = `Bearer ${token}`;
    }
    return merged;
};

const toObject = (value) => (value && typeof value === "object" && !Array.isArray(value) ? value : {});

const toNumber = (value, fallback = 0) => {
    if (value === null || value === undefined || value === "") return fallback;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const toBool = (value) => {
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value !== 0;
    const normalized = String(value || "").trim().toLowerCase();
    if (!normalized) return false;
    return ["1", "true", "yes", "y", "oui"].includes(normalized);
};

const toStringList = (value) => {
    const rawList = Array.isArray(value)
        ? value
        : (typeof value === "string" ? value.split(",") : []);
    const seen = new Set();
    const normalized = [];
    rawList.forEach((item) => {
        if (item === null || item === undefined) return;
        const text = String(item).trim();
        if (!text) return;
        const key = text.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        normalized.push(text);
    });
    return normalized;
};

export const normalizeAnalysisResult = (payload) => {
    const source = toObject(payload);
    const routingSource = toObject(source.routing);
    const rgpdSource = toObject(source.rgpd);
    const metaSource = toObject(source.meta_analysis);

    const resolvedTier = clamp(
        Math.round(toNumber(source.tier ?? routingSource.tier, 1)),
        1,
        3
    );
    const resolvedConfidence = clamp(
        toNumber(source.confidence ?? routingSource.confidence, 0),
        0,
        1
    );

    const tagsFromPayload = Array.isArray(source.tags) ? source.tags : source.extraction?.tags;
    const tags = toStringList(tagsFromPayload);

    return {
        ...source,
        id: source.id ?? source.ID ?? "",
        tags,
        routing: {
            ...routingSource,
            tier: resolvedTier,
            confidence: resolvedConfidence,
            reason: routingSource.reason ? String(routingSource.reason) : null
        },
        tier: resolvedTier,
        confidence: resolvedConfidence,
        rgpd: {
            ...rgpdSource,
            contains_sensitive: toBool(rgpdSource.contains_sensitive),
            categories_detected: toStringList(rgpdSource.categories_detected)
        },
        meta_analysis: {
            ...metaSource,
            quality_score: toNumber(metaSource.quality_score, 0),
            missing_info: toStringList(metaSource.missing_info),
            risk_flags: toStringList(metaSource.risk_flags)
        },
        pilier_1_univers_produit: toObject(source.pilier_1_univers_produit),
        pilier_2_profil_client: toObject(source.pilier_2_profil_client),
        pilier_3_hospitalite_care: toObject(source.pilier_3_hospitalite_care),
        pilier_4_action_business: toObject(source.pilier_4_action_business)
    };
};

export const apiFetch = (path, options = {}) => {
    const nextOptions = { ...options };
    nextOptions.headers = buildHeadersWithAuth(options.headers);
    
    return fetch(apiUrl(path), nextOptions).then((response) => {
        // Handle 401 errors - redirect to login
        if (response.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
            return response;
        }
        return response;
    });
};
