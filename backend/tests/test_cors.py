"""With CORS_ORIGIN unset (the conftest default), the API must NOT echo a
wildcard Access-Control-Allow-Origin — cross-origin access is denied by default."""


def test_no_wildcard_cors_by_default(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
    acao = r.headers.get("access-control-allow-origin")
    assert acao != "*"
    assert acao is None  # unlisted origin gets no CORS grant at all
