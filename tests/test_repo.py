# tests/test_repo_miner.py

import os
import pandas as pd
import pytest
from datetime import datetime, timedelta
from src.repo_miner import fetch_commits, fetch_issues

# --- Helpers for dummy GitHub API objects ---

class DummyAuthor:
    def __init__(self, name, email, date):
        self.name = name
        self.email = email
        self.date = date

class DummyCommitCommit:
    def __init__(self, author, message):
        self.author = author
        self.message = message

class DummyCommit:
    def __init__(self, sha, author, email, date, message):
        self.sha = sha
        self.commit = DummyCommitCommit(DummyAuthor(author, email, date), message)

class DummyUser:
    def __init__(self, login):
        self.login = login

class DummyIssue:
    def __init__(self, id_, number, title, user, state, created_at, closed_at, comments, is_pr=False):
        self.id = id_
        self.number = number
        self.title = title
        self.user = DummyUser(user)
        self.state = state
        self.created_at = created_at
        self.closed_at = closed_at
        self.comments = comments
        # attribute only on pull requests
        self.pull_request = DummyUser("pr") if is_pr else None

class DummyRepo:
    def __init__(self, commits, issues):
        self._commits = commits
        self._issues = issues

    def get_commits(self):
        return self._commits

    def get_issues(self, state="all"):
        # filter by state
        if state == "all":
            return self._issues
        return [i for i in self._issues if i.state == state]

class DummyGithub:
    def __init__(self, token):
        assert token == "fake-token"
        self._repo = None
    
    def get_repo(self, repo_name):
        # ignore repo_name; return repo set in test fixture
        return self._repo

# Global instance to be used by all tests
gh_instance = DummyGithub("fake-token")

@pytest.fixture(autouse=True)
def patch_env_and_github(monkeypatch):
    # Set fake token
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    # Patch Github class to return our global instance
    def mock_github(token):
        return gh_instance
    monkeypatch.setattr("src.repo_miner.Github", mock_github)

# --- Tests for fetch_commits ---
# An example test case
def test_fetch_commits_basic(monkeypatch):
    # Setup dummy commits
    now = datetime.now()
    commits = [
        DummyCommit("sha1", "Alice", "a@example.com", now, "Initial commit\nDetails"),
        DummyCommit("sha2", "Bob", "b@example.com", now - timedelta(days=1), "Bug fix")
    ]
    gh_instance._repo = DummyRepo(commits, [])
    df = fetch_commits("any/repo")
    assert list(df.columns) == ["sha", "author", "email", "date", "message"]
    assert len(df) == 2
    assert df.iloc[0]["message"] == "Initial commit"

def test_fetch_commits_limit(monkeypatch):
    # More commits than max_commits
    now = datetime.now()
    commits = [
        DummyCommit("sha1", "Alice", "a@example.com", now, "Commit 1"),
        DummyCommit("sha2", "Bob", "b@example.com", now - timedelta(days=1), "Commit 2"),
        DummyCommit("sha3", "Charlie", "c@example.com", now - timedelta(days=2), "Commit 3"),
        DummyCommit("sha4", "David", "d@example.com", now - timedelta(days=3), "Commit 4"),
        DummyCommit("sha5", "Eve", "e@example.com", now - timedelta(days=4), "Commit 5")
    ]
    gh_instance._repo = DummyRepo(commits, [])
    
    # Test with max_commits=3
    df = fetch_commits("any/repo", max_commits=3)
    assert len(df) == 3
    assert df.iloc[0]["sha"] == "sha1"
    assert df.iloc[1]["sha"] == "sha2"
    assert df.iloc[2]["sha"] == "sha3"

def test_fetch_commits_empty(monkeypatch):
    # Test that fetch_commits returns empty DataFrame when no commits exist
    gh_instance._repo = DummyRepo([], [])
    df = fetch_commits("any/repo")
    assert len(df) == 0
    # When empty, pandas DataFrame has no columns, which is expected behavior
    assert len(df.columns) == 0

# --- Tests for fetch_issues ---

def test_fetch_issues_excludes_prs(monkeypatch):
    """Test that fetch_issues excludes pull requests and only returns issues."""
    now = datetime.now()
    issues = [
        DummyIssue(1, 1, "Bug report", "alice", "open", now, None, 0, is_pr=False),
        DummyIssue(2, 2, "Feature request", "bob", "closed", now - timedelta(days=1), now, 3, is_pr=False),
        DummyIssue(3, 3, "Pull request", "charlie", "open", now, None, 0, is_pr=True),  # This should be excluded
    ]
    gh_instance._repo = DummyRepo([], issues)
    
    df = fetch_issues("any/repo")
    
    # Should only have 2 issues (PR excluded)
    assert len(df) == 2
    assert list(df.columns) == ["id", "number", "title", "user", "state", "created_at", "closed_at", "comments", "open_duration_days"]
    assert df.iloc[0]["title"] == "Bug report"
    assert df.iloc[1]["title"] == "Feature request"
    # Verify no PRs are included
    assert "Pull request" not in df["title"].values

def test_fetch_issues_date_normalization(monkeypatch):
    """Test that dates are properly normalized to ISO-8601 format."""
    now = datetime.now()
    created_at = now - timedelta(days=5)
    closed_at = now - timedelta(days=2)
    
    issues = [
        DummyIssue(1, 1, "Test issue", "alice", "closed", created_at, closed_at, 1, is_pr=False),
    ]
    gh_instance._repo = DummyRepo([], issues)
    
    df = fetch_issues("any/repo")
    
    # Check that dates are in ISO format
    assert df.iloc[0]["created_at"] == created_at.isoformat()
    assert df.iloc[0]["closed_at"] == closed_at.isoformat()
    
    # Verify the format is ISO-8601 (contains 'T' and timezone info)
    assert 'T' in df.iloc[0]["created_at"]
    assert 'T' in df.iloc[0]["closed_at"]

def test_fetch_issues_open_duration_calculation(monkeypatch):
    """Test that open_duration_days is calculated correctly."""
    now = datetime.now()
    created_at = now - timedelta(days=10, hours=12)  # 10.5 days ago
    closed_at = now - timedelta(days=3, hours=6)     # 3.25 days ago
    expected_days = 7  # 10.5 - 3.25 = 7.25, but we use .days which gives 7
    
    issues = [
        DummyIssue(1, 1, "Closed issue", "alice", "closed", created_at, closed_at, 2, is_pr=False),
        DummyIssue(2, 2, "Open issue", "bob", "open", now - timedelta(days=5), None, 0, is_pr=False),
    ]
    gh_instance._repo = DummyRepo([], issues)
    
    df = fetch_issues("any/repo")
    
    # Check open_duration_days calculation
    closed_issue = df[df["state"] == "closed"].iloc[0]
    open_issue = df[df["state"] == "open"].iloc[0]
    
    assert closed_issue["open_duration_days"] == expected_days
    # Open issues should have NaN (pandas converts None to NaN in DataFrames)
    import math
    assert math.isnan(open_issue["open_duration_days"])
