import pytest
from pydantic import ValidationError

from src.web.register_schema import RegisterApiBody


def test_telegram_chat_id_strips_spaces():
    b = RegisterApiBody(telegram_chat_id="-100 123 456 789", stack=["react"])
    assert b.telegram_chat_id == "-100123456789"


def test_stack_filters_unknown():
    b = RegisterApiBody(telegram_chat_id="-100123456789", stack=["react", "unknown_stack"])
    assert b.stack == ["react"]


def test_invalid_chat_id_rejected():
    with pytest.raises(ValidationError):
        RegisterApiBody(telegram_chat_id="not-digits", stack=[])
