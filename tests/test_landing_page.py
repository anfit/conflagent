import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from conflagent import app  # noqa: E402  pylint: disable=wrong-import-position


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_landing_page_serves_static_content(client):
    response = client.get('/')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'landing__hero-title' in html
    assert 'Welcome to Conflagent' in html
    assert 'landing__hero-subtitle' in html
    assert 'View API Specification' not in html
