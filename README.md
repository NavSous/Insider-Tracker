# Insider Trading Tracker

This application currently fetches and analyzes insider trading data from Finviz.com. It helps track significant insider trades and provides a summary of recent insider trading activity. 

## Features

- Fetches real-time insider trading data from Finviz
- Processes and cleans the data for analysis
- Identifies significant trades (>$100,000)
- Provides a summary of recent insider trading activity
- Displays top trades by value

## Requirements

- Python 3.7+
- Required packages listed in `requirements.txt`

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/insider-tracker.git
cd insider-tracker
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python main.py
```

The application will:
1. Fetch the latest insider trading data
2. Process and analyze the data
3. Display a summary of recent insider trading activity
4. Show the top 5 largest trades

## Output Example

```
=== Insider Trading Summary ===
Total number of trades: 125
Number of significant trades (>$100k): 45

Top 5 largest trades:
   Ticker    Owner           Relationship    Date        Transaction    Value ($)
1  AAPL     John Doe        Director        2023-05-15  Sale          2500000.0
2  MSFT     Jane Smith      CEO             2023-05-15  Buy           1800000.0
...
```