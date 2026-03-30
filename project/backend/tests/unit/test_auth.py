from src.api.auth import extract_api_key, hash_api_key


def test_extract_api_key_x_header():
    assert extract_api_key(None, " abc ") == "abc"


def test_extract_api_key_bearer():
    assert extract_api_key("Bearer mytoken", None) == "mytoken"
    assert extract_api_key("bearer x", None) == "x"


def test_extract_api_key_priority_x_over_bearer():
    assert extract_api_key("Bearer a", "b") == "b"


def test_extract_api_key_empty():
    assert extract_api_key(None, None) is None
    assert extract_api_key("", "") is None
    assert extract_api_key("Basic xxx", None) is None


def test_hash_api_key_deterministic(monkeypatch):
    monkeypatch.setenv("API_KEY_PEPPER", "pepper-1")
    a = hash_api_key("same")
    b = hash_api_key("same")
    assert a == b
    assert len(a) == 64
    c = hash_api_key("other")
    assert c != a
