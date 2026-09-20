# Deployment

Use PostgreSQL, Gunicorn and Nginx in production. Set `FLASK_CONFIG=app.config.production.ProductionConfig`, strong random secrets, production database credentials, HTTPS, secure cookies, and a shared rate-limit backend. Keep uploads/reports on protected persistent storage and back them up separately from the application container.
