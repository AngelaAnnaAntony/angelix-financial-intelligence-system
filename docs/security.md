# Security

- Secrets belong in `.env`, never source control.
- Passwords use bcrypt.
- Uploaded files use random private names and organization-scoped directories.
- Generated reports are stored outside static assets.
- SQLAlchemy ORM is used for database access.
- Organization membership is checked before organization resources.
- AI context must be minimized and must not contain credentials or unrelated user data.
- Production deployment should enable HTTPS and secure cookies.
