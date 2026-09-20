# Angelix Architecture

Layered architecture:
Routes → Controllers/Services → Repositories/Models → PostgreSQL.

Analytics and financial statement calculations are deterministic. AI is isolated under `app/ai` and configured through environment variables. Uploads and generated reports remain private.

Core workflow:
Upload → document processing/OCR → transaction records → classification/review → statements → analytics → health/advisor/reporting.
