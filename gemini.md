# Project Context: CRM in AEC Framework, EMEK ERP, and Pearson CAS

## 🧭 Vision & Core Philosophy
* **The Framework:** "CRM in AEC" is not just a label; it is a functional framework prioritizing interoperability and structured data exchange between all actors in a building process.
* **Intelligence Layer:** EMEK ERP acts as the "Single Source of Truth" and data intelligence backbone. **arkhon** (CRM) and **Pearson** (Academic) serve as specialized, purpose-built interfaces relying on this core.
* **Design Aesthetic:** Bauhaus-inspired (specifically László Moholy-Nagy). Clean, functional, automated, with a heavy emphasis on typography, geometric clarity, and visual hierarchy.
* **Zero-Lock-in:** Strict "Microsoft-free" workflow. All generated templates and outputs must be open-standard.

## 🏗️ System Architecture & Tech Stack
* **Core Hub:** A unified Python/Flask ecosystem.
* **Stack:** Python, Flask, SQLAlchemy, Jinja2, ReportLab, Pandoc.
* **Development Environment:** VS Code utilizing Gemini Code Assist as an "Architect's Studio" for code execution and context management.
* **Document Pipeline:** 1. **Live Collaboration:** Bi-directional sync with Google Docs/Drive API (OAuth 2.0).
    2. **Archival & Export:** Native generation of OASIS OpenDocument Format (`.odt`, `.ods`) and PDF via ReportLab/Pandoc.

## 🌍 Environment & Deployment Strategy
Strict separation between Development and Production environments is mandatory. The AI must respect these boundaries for all routing, authentication, and database operations.

* **Local Development (The Sandbox):**
    * **Entry Point:** `run.py`
    * **Domain:** Strictly `http://127.0.0.1:5000` (Never use `localhost` to ensure OAuth callback consistency).
    * **Environment:** `FLASK_ENV=development`
    * **Auth/Security:** `AUTHLIB_INSECURE_TRANSPORT = '1'` is permitted. Session cookies should be `Secure=False`.
    * **Database:** Uses local SQLite (`data/portal.db`) with dummy seed data.

* **Production (The Live Hub):**
    * **Entry Point:** `serve.py` (Waitress/Production WSGI).
    * **Domain:** `https://pearson.crminaec.com`
    * **Infrastructure:** Published to the internet via Cloudflare Tunnels. 
    * **Environment:** `FLASK_ENV=production`
    * **Auth/Security:** Must use `ProxyFix` to parse `X-Forwarded-Proto` headers from Cloudflare so Flask generates `https://` URLs for Google OAuth. `SESSION_COOKIE_SECURE = True` is mandatory.
    * **Database:** Connects to the live production database. No destructive structural drops (`drop_all`) are permitted here.

* **Authentication Protocol:** The OAuth 2.0 system must dynamically handle both environments. Callback URIs must be generated using `url_for('auth.google_callback', _external=True)` rather than hardcoded config strings to ensure the state matches the active environment.

## 🎯 The Three Pillars (Project Goals)
1. **Academic (Pearson CAS):** Develop a Course Automation System based on Pearson HND5 specifications to transform database content into multi-format teaching materials.
2. **Corporate (arkhon CRM):** Build the front-facing client management system. It must securely collect and structure all legal evidence for hassle-free operations from the initial meeting through after-sales services.
3. **Backbone (EMEK ERP):** Develop a comprehensive corporate library and database that organizes all data, serving as the intelligence engine for both the CRM and the CAS.

## ⚖️ Standards & Compliance
* **Identity & Address Structure:** Adhere strictly to **OASIS CIQ** (Customer Information Quality) for high-fidelity identity management and relational integrity across systems.
* **Data Privacy:** All data handling must strictly follow **Turkish KVKK** guidelines. No logging of sensitive PII without explicit consent; implement strict data minimization in SQLAlchemy models.
* **Document Standards:** Ensure compliance with **OASIS ODF** for all generated text and spreadsheet files.

## 🧩 Interoperability & Frontend Logic
* **Common Data Model (CDM):** Every entity must be relatable across the three systems. A "Student" in Pearson may also be a "Client" in arkhon or a "Lead" in EMEK.
* **Relational Integrity:** Utilize unique UUIDs or composite keys to ensure zero-collision when importing CSV data from external AEC actors.
* **KISS Principle (UI/UX):** Keep It Simple and Short. Design each main route (Pearson, CRM, EMEK) as a modular **Single Page Application (SPA)** to reduce friction.