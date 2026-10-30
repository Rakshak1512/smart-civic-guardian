-- Smart Civic Guardian - Seed Data Reference
-- NOTE: Passwords must be securely hashed (werkzeug generate_password_hash),
-- so actual seeding is performed automatically by Python at first run
-- (see backend/app/seed.py). This file documents the demo data created.

-- Demo Users
-- citizen@example.com   | password: Citizen@123  | role: citizen
-- citizen2@example.com  | password: Citizen@123  | role: citizen
-- admin@example.com     | password: Admin@123    | role: authority (BBMP - Sanitation)
-- water@example.com     | password: Admin@123    | role: authority (BWSSB - Water Supply)

-- Demo Complaints (created automatically with varied category/priority/status/location/date)
-- so that the analytics dashboard has data to display immediately after setup.
