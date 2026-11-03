import json
import logging

from apps.core.logging import REDACTED, JsonFormatter, RequestIdFilter, SensitiveDataFilter


def _record(msg, args=None, **extra):
    record = logging.LogRecord("apps.test", logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    SensitiveDataFilter().filter(record)
    RequestIdFilter().filter(record)
    return record


def test_secret_pairs_in_message_are_redacted():
    record = _record("verify otp=482913 token: abc.def")
    assert "482913" not in record.getMessage()
    assert "abc.def" not in record.getMessage()


def test_phone_numbers_are_masked_to_last_three_digits():
    record = _record("sent to %s", ("+963912345678",))
    assert record.getMessage() == "sent to ***678"


def test_sensitive_extra_fields_are_redacted():
    record = _record("login", otp="123456", headers={"Cookie": "sid=1", "Accept": "json"})
    assert record.otp == REDACTED
    assert record.headers == {"Cookie": REDACTED, "Accept": "json"}


def test_json_formatter_emits_stable_fields():
    record = _record("hello")
    line = json.loads(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s").format(record))
    assert line["level"] == "INFO"
    assert line["logger"] == "apps.test"
    assert line["message"] == "hello"
    assert "request_id" in line


def test_identifiers_and_numbers_are_not_mistaken_for_phones():
    text = "task 0942c2ee-4655-465b-0bfd-1b8040000000 ran 1730000344.248691 order ART-2026-000125"
    assert _record(text).getMessage() == text


def test_bare_local_number_is_masked():
    assert _record("call 0912345678 now").getMessage() == "call ***678 now"
