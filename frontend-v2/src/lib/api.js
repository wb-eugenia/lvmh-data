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

export const apiFetch = (path, options) => fetch(apiUrl(path), options);
