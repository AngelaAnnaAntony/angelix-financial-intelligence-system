from app import create_app
def test_health():
    app=create_app("app.config.testing.TestingConfig")
    client=app.test_client()
    with app.app_context():
        from app.extensions import db
        db.create_all()
    assert client.get("/health").status_code == 200
