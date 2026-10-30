/**
 * ====================================================================
 * Smart Civic Guardian - Centralized Frontend API Client
 * All frontend requests to the Backend REST API use API_BASE_URL.
 * ====================================================================
 */

// Centralized Backend REST API Base URL
// Can be overridden via window.API_BASE_URL or window.FRONTEND_ENV.BACKEND_URL
const API_BASE_URL = (
    (typeof window !== "undefined" && window.FRONTEND_ENV && window.FRONTEND_ENV.BACKEND_URL) ||
    (typeof window !== "undefined" && window.API_BASE_URL) ||
    "http://localhost:5000"
).replace(/\/+$/, "");

window.API_BASE_URL = API_BASE_URL;

class ApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }

    async request(endpoint, options = {}) {
        const url = endpoint.startsWith("http") ? endpoint : `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

        const defaultHeaders = {};
        if (!(options.body instanceof FormData)) {
            defaultHeaders["Content-Type"] = "application/json";
        }

        const config = {
            ...options,
            credentials: "include", // Required for cross-origin session authentication
            headers: {
                ...defaultHeaders,
                ...(options.headers || {}),
            },
        };

        if (options.body && !(options.body instanceof FormData) && typeof options.body === "object") {
            config.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, config);
            const contentType = response.headers.get("content-type") || "";
            let data = null;

            if (contentType.includes("application/json")) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                const message = (data && data.message) || (data && data.error) || response.statusText;
                const err = new Error(message);
                err.status = response.status;
                err.data = data;
                throw err;
            }

            return data;
        } catch (error) {
            console.error(`[API Error] ${options.method || "GET"} ${url}:`, error);
            throw error;
        }
    }

    get(endpoint, headers = {}) {
        return this.request(endpoint, { method: "GET", headers });
    }

    post(endpoint, body = {}, headers = {}) {
        return this.request(endpoint, { method: "POST", body, headers });
    }

    postMultipart(endpoint, formData, headers = {}) {
        return this.request(endpoint, { method: "POST", body: formData, headers });
    }

    put(endpoint, body = {}, headers = {}) {
        return this.request(endpoint, { method: "PUT", body, headers });
    }

    delete(endpoint, headers = {}) {
        return this.request(endpoint, { method: "DELETE", headers });
    }

    // Auth methods
    async checkHealth() {
        return this.get("/api/health");
    }

    async getCurrentUser() {
        return this.get("/api/auth/me");
    }

    async login(email, password) {
        return this.post("/api/auth/login", { email, password });
    }

    async register(userData) {
        return this.post("/api/auth/register", userData);
    }

    async logout() {
        return this.post("/api/auth/logout", {});
    }

    // Complaints methods
    async getComplaints(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(`/api/complaints${query ? `?${query}` : ""}`);
    }

    async getMyComplaints() {
        return this.get("/api/complaints/my");
    }

    async getComplaintDetail(id) {
        return this.get(`/api/complaints/${id}`);
    }

    async submitComplaint(formData) {
        return this.postMultipart("/api/complaints", formData);
    }

    async analyzePhoto(formData) {
        return this.postMultipart("/api/complaints/analyze", formData);
    }

    async submitFeedback(complaintId, rating, comment) {
        return this.post(`/api/complaints/${complaintId}/feedback`, { rating, comment });
    }

    // Admin & Authority methods
    async getAdminDashboard() {
        return this.get("/api/admin/dashboard");
    }

    async getAdminComplaints(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.get(`/api/admin/complaints${query ? `?${query}` : ""}`);
    }

    async updateStatus(complaintId, formData) {
        return this.postMultipart(`/api/admin/complaints/${complaintId}/status`, formData);
    }

    async assignComplaint(complaintId, assignedTo) {
        return this.post(`/api/admin/complaints/${complaintId}/assign`, { assigned_to: assignedTo });
    }

    async getAuthorities() {
        return this.get("/api/admin/authorities");
    }

    async getMapComplaints() {
        return this.get("/api/admin/map");
    }

    // Analytics & Notifications
    async getAnalyticsSummary() {
        return this.get("/api/analytics/summary");
    }

    async getNotifications() {
        return this.get("/api/notifications");
    }

    async markNotificationsRead() {
        return this.post("/api/notifications/read", {});
    }

    async submitContact(data) {
        return this.post("/api/contact", data);
    }
}

// Global API instance available to all scripts
const api = new ApiClient(API_BASE_URL);
window.api = api;
console.log(`[Smart Civic Guardian] Frontend connected to Backend API at: ${API_BASE_URL}`);

