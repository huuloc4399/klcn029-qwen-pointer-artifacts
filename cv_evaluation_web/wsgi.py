"""WSGI entry point used by Render/Gunicorn."""

from app import create_app


application = create_app()
