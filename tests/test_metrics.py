from __future__ import annotations

from typing import Dict

from conflagent import app


def _get_metric_value(metrics_text: str, metric: str, labels: Dict[str, str]) -> float:
    label_repr = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
    target = f"{metric}{{{label_repr}}}"

    for line in metrics_text.splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith(target):
            return float(line.split(" ", 1)[1])
    return 0.0


def test_metrics_collect_http_requests_for_root_route():
    client = app.test_client()

    before_metrics = client.get("/metrics")
    assert before_metrics.status_code == 200
    before_text = before_metrics.data.decode("utf-8")

    counter_labels = {"method": "GET", "route": "/", "status": "200"}
    histogram_labels = {"method": "GET", "route": "/"}
    gauge_labels = {"route": "/"}

    before_count = _get_metric_value(before_text, "http_requests_total", counter_labels)
    before_duration_count = _get_metric_value(
        before_text, "http_request_duration_seconds_count", histogram_labels
    )

    response = client.get("/")
    assert response.status_code == 200

    after_metrics = client.get("/metrics")
    assert after_metrics.status_code == 200
    after_text = after_metrics.data.decode("utf-8")

    after_count = _get_metric_value(after_text, "http_requests_total", counter_labels)
    after_duration_count = _get_metric_value(
        after_text, "http_request_duration_seconds_count", histogram_labels
    )
    gauge_value = _get_metric_value(after_text, "http_requests_in_progress", gauge_labels)

    assert after_count == before_count + 1
    assert after_duration_count == before_duration_count + 1
    assert gauge_value == 0.0
