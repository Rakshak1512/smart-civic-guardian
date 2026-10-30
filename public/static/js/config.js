/**
 * Frontend Runtime Configuration
 * Defines separate URLs for Frontend client and Backend REST API.
 */
window.FRONTEND_ENV = window.FRONTEND_ENV || {
    FRONTEND_URL: window.FRONTEND_URL || "http://localhost:3000",
    BACKEND_URL: window.BACKEND_URL || "http://localhost:5000",
};

window.API_BASE_URL = window.FRONTEND_ENV.BACKEND_URL;

console.log("[Smart Civic Guardian] Frontend URL:", window.FRONTEND_ENV.FRONTEND_URL);
console.log("[Smart Civic Guardian] Backend REST API URL:", window.FRONTEND_ENV.BACKEND_URL);
