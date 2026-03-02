# Version: 0.1.0

from ghkit.http.pagination import parse_link_header


def test_parse_link_header_empty():
    assert parse_link_header("") == []


def test_parse_link_header_basic():
    value = '<https://api.github.com/resource?page=2>; rel="next", <https://api.github.com/resource?page=5>; rel="last"'
    links = parse_link_header(value)
    rels = {l.rel for l in links}
    assert "next" in rels
    assert "last" in rels
