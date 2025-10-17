#!/usr/bin/env python3
"""
repo_miner.py

A command-line tool to:
  1) Fetch and normalize commit data from GitHub
  2) Fetch and normalize issue data from GitHub (excluding pull requests)

Sub-commands:
  - fetch-commits
  - fetch-issues
"""

import os
import argparse
import pandas as pd
from datetime import datetime
from github import Github

def load_env_file(env_path='.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load environment variables from .env file
load_env_file()

def fetch_commits(repo_full_name: str, max_commits: int = None) -> pd.DataFrame:
    """
    Fetch up to `max_commits` from the specified GitHub repository.
    Returns a DataFrame with columns: sha, author, email, date, message.
    """
    # 1) Read GitHub token from environment
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    # 2) Initialize GitHub client and get the repo
    g = Github(token)
    repo = g.get_repo(repo_full_name)
    
    # 3) Fetch commit objects (paginated by PyGitHub)
    commits = []
    for commit in repo.get_commits():
        if max_commits and len(commits) >= max_commits:
            break
            
        # 4) Normalize each commit into a record dict
        commit_data = {
            'sha': commit.sha,
            'author': commit.commit.author.name if commit.commit.author else 'Unknown',
            'email': commit.commit.author.email if commit.commit.author else 'Unknown',
            'date': commit.commit.author.date.isoformat() if commit.commit.author else 'Unknown',
            'message': commit.commit.message.split('\n')[0] if commit.commit.message else 'No message'
        }
        commits.append(commit_data)
    
    # 5) Build DataFrame from records
    return pd.DataFrame(commits)


def fetch_issues(repo_full_name: str, state: str = "all", max_issues: int = None) -> pd.DataFrame:
    """
    Fetch up to `max_issues` from the specified GitHub repository.
    Skips pull requests and returns only issues.
    Returns a DataFrame with columns: id, number, title, user, state, created_at, closed_at, comments, open_duration_days.
    """
    # 1) Read GitHub token from environment
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    # 2) Initialize GitHub client and get the repo
    g = Github(token)
    repo = g.get_repo(repo_full_name)
    
    # 3) Fetch issue objects (paginated by PyGitHub)
    issues = []
    for issue in repo.get_issues(state=state):
        if max_issues and len(issues) >= max_issues:
            break
            
        # 4) Skip pull requests (they have pull_request attribute)
        if hasattr(issue, 'pull_request') and issue.pull_request is not None:
            continue
            
        # 5) Normalize each issue into a record dict
        created_at = issue.created_at.isoformat() if issue.created_at else None
        closed_at = issue.closed_at.isoformat() if issue.closed_at else None
        
        # Calculate open_duration_days
        open_duration_days = None
        if created_at and closed_at:
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            closed_dt = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
            open_duration_days = (closed_dt - created_dt).days
        
        issue_data = {
            'id': issue.id,
            'number': issue.number,
            'title': issue.title,
            'user': issue.user.login if issue.user else 'Unknown',
            'state': issue.state,
            'created_at': created_at,
            'closed_at': closed_at,
            'comments': issue.comments,
            'open_duration_days': open_duration_days
        }
        issues.append(issue_data)
    
    # 6) Build DataFrame from records
    return pd.DataFrame(issues)
    
def merge_and_summarize(commits_df, issues_df) -> None:
    """
    Merge commits and issues on date and summarize the data.
    Computes and prints:
    - Top 5 committers by count
    - Issue close rate (closed / total)
    - Average issue open duration
    """
    # Convert date columns to datetime for proper joining
    commits_df['date'] = pd.to_datetime(commits_df['date'])
    issues_df['created_at'] = pd.to_datetime(issues_df['created_at'])
    
    # Create date columns for joining (by day)
    commits_df['date_day'] = commits_df['date'].dt.date
    issues_df['created_date'] = issues_df['created_at'].dt.date
    
    # Join commits and issues on date
    merged_df = pd.merge(commits_df, issues_df, left_on='date_day', right_on='created_date', how='outer')
    
    print("SUMMARY STATISTICS")
    print()
    
    # Top 5 committers by count
    print("Top 5 committers by commit count:")
    top_committers = commits_df['author'].value_counts().head(5)
    for author, count in top_committers.items():
        print(f"  {author}: {count} commits")
    print()
    
    # Issue close rate
    total_issues = len(issues_df)
    closed_issues = len(issues_df[issues_df['state'] == 'closed'])
    close_rate = (closed_issues / total_issues * 100) if total_issues > 0 else 0
    print(f"Issue close rate: {close_rate:.1f}% ({closed_issues}/{total_issues})")
    print()
    
    # Average issue open duration (only for closed issues)
    closed_issues_with_duration = issues_df[
        (issues_df['state'] == 'closed') & 
        (issues_df['open_duration_days'].notna())
    ]
    if len(closed_issues_with_duration) > 0:
        avg_duration = closed_issues_with_duration['open_duration_days'].mean()
        print(f"Average issue open duration: {avg_duration:.1f} days")
    else:
        print("Average issue open duration: N/A (no closed issues with duration data)")
    print()
    
    return merged_df

def main():
    """
    Parse command-line arguments and dispatch to sub-commands.
    """
    parser = argparse.ArgumentParser(
        prog="repo_miner",
        description="Fetch GitHub commits/issues and summarize them"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sub-command: fetch-commits
    c1 = subparsers.add_parser("fetch-commits", help="Fetch commits and save to CSV")
    c1.add_argument("--repo", required=True, help="Repository in owner/repo format")
    c1.add_argument("--max",  type=int, dest="max_commits",
                    help="Max number of commits to fetch")
    c1.add_argument("--out",  required=True, help="Path to output commits CSV")

    # Sub-command: fetch-issues
    c2 = subparsers.add_parser("fetch-issues", help="Fetch issues and save to CSV")
    c2.add_argument("--repo", required=True, help="Repository in owner/repo format")
    c2.add_argument("--state", choices=["all", "open", "closed"], default="all",
                    help="Issue state filter (default: all)")
    c2.add_argument("--max", type=int, dest="max_issues",
                    help="Max number of issues to fetch")
    c2.add_argument("--out", required=True, help="Path to output issues CSV")

    # Sub-command: summarize
    c3 = subparsers.add_parser("summarize", help="Summarize commits and issues from CSV files")
    c3.add_argument("--commits", required=True, help="Path to commits CSV file")
    c3.add_argument("--issues", required=True, help="Path to issues CSV file")

    args = parser.parse_args()

    # Dispatch based on selected command
    if args.command == "fetch-commits":
        df = fetch_commits(args.repo, args.max_commits)
        df.to_csv(args.out, index=False)
        print(f"Saved {len(df)} commits to {args.out}")
    elif args.command == "fetch-issues":
        df = fetch_issues(args.repo, args.state, args.max_issues)
        df.to_csv(args.out, index=False)
        print(f"Saved {len(df)} issues to {args.out}")
    elif args.command == "summarize":
        # Load CSV files
        commits_df = pd.read_csv(args.commits)
        issues_df = pd.read_csv(args.issues)
        
        # Run summary analysis
        merge_and_summarize(commits_df, issues_df)

if __name__ == "__main__":
    main()
