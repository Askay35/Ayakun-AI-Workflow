import json
import logging

from core.logging import JsonFormatter, output_preview


def test_output_preview_keeps_ai_usage() -> None:
    preview = output_preview({
        "text": "итог",
        "model": "deepseek-flash",
        "truncated": False,
        "usage": {"input_tokens": 59, "output_tokens": 331},
    })
    payload = json.loads(preview)
    assert payload["text"] == "итог"
    assert payload["usage"]["output_tokens"] == 331


def test_json_formatter_includes_event_and_credits() -> None:
    record = logging.LogRecord(
        name="execution.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Звено выполнено",
        args=(),
        exc_info=None,
    )
    record.event = "node.succeeded"
    record.credits = "0.23144"
    record.node_type = "prompt"
    line = JsonFormatter("worker").format(record)
    payload = json.loads(line)
    assert payload["event"] == "node.succeeded"
    assert payload["credits"] == "0.23144"
    assert payload["service"] == "worker"
    assert payload["msg"] == "Звено выполнено"
