# Data Collection LTL3735

A Python project for data collection and repository mining.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

The repo_miner tool provides three main commands:

### Fetch Commits
```bash
python -m src.repo_miner fetch-commits --repo owner/repo --out commits.csv
```

### Fetch Issues
```bash
python -m src.repo_miner fetch-issues --repo owner/repo --out issues.csv
```

### Summarize Data
```bash
python -m src.repo_miner summarize --commits commits.csv --issues issues.csv
```

The summarize command analyzes the data and prints:
- Top 5 committers by commit count
- Issue close rate (closed / total)
- Average issue open duration

## Sample Results

Here's an example output from the summarize command:

```
SUMMARY STATISTICS

Top 5 committers by commit count:
  John Doe: 4 commits
  Jane Smith: 3 commits
  Bob Wilson: 2 commits
  Alice Brown: 1 commits

Issue close rate: 60.0% (6/10)

Average issue open duration: 1.8 days
```

## Development

Run tests:
```bash
pytest
```