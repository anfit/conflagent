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
    assert 'Welcome to Conflagent' in html
    assert 'View API Specification' in html
    assert 'Conflagent' in html
    assert 'v1.0.0' in html
    assert 'Built 2024-05-01' in html
    assert 'Commit abc1234' in html
