# Version: 0.1.0

from ghkit.github.urlparse import parse_github_url


def test_parse_repo_url():
    u = parse_github_url("https://github.com/octocat/Hello-World")
    assert u.owner == "octocat"
    assert u.repo == "Hello-World"
    assert u.pr_number is None
    assert u.issue_number is None


def test_parse_pr_url():
    u = parse_github_url("https://github.com/octocat/Hello-World/pull/123")
    assert u.owner == "octocat"
    assert u.repo == "Hello-World"
    assert u.pr_number == 123


def test_parse_issue_url():
    u = parse_github_url("https://github.com/octocat/Hello-World/issues/9")
    assert u.issue_number == 9
