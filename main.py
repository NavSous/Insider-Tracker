import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Union
import os
from alpha_vantage.fundamentaldata import FundamentalData
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class InsiderTracker:
    def __init__(self):
        self.base_url = "https://finviz.com/insidertrading.ashx"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self._cached_data = None
        self._last_fetch_time = None
        self._cache_duration = timedelta(minutes=5)
        self._market_cap_cache = {}
        
        # Load Alpha Vantage API key from environment
        load_dotenv()
        self.av_api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.av_api_key:
            logger.warning("Alpha Vantage API key not found. Market cap data will not be available.")
        else:
            self.fd = FundamentalData(key=self.av_api_key)

    def _get_market_cap(self, ticker: str) -> float:
        """Get market cap for a ticker using Alpha Vantage."""
        if not self.av_api_key:
            return 0
            
        # Check cache first
        if ticker in self._market_cap_cache:
            return self._market_cap_cache[ticker]
            
        try:
            # Get company overview from Alpha Vantage
            overview, _ = self.fd.get_company_overview(ticker)
            market_cap = float(overview.get('MarketCapitalization', 0))
            
            # Cache the result
            self._market_cap_cache[ticker] = market_cap
            return market_cap
        except Exception as e:
            logger.warning(f"Could not fetch market cap for {ticker}: {str(e)}")
            return 0

    def fetch_insider_data(self, use_cache: bool = True) -> pd.DataFrame:
        """Fetch insider trading data from Finviz with caching support."""
        # Check if we can use cached data
        if use_cache and self._cached_data is not None and self._last_fetch_time is not None:
            if datetime.now() - self._last_fetch_time < self._cache_duration:
                logger.info("Using cached insider trading data")
                return self._cached_data.copy()

        try:
            logger.info("Fetching insider trading data from Finviz...")
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try finding table by ID first
            table = soup.find('table', {'id': 'insider-table'})
            
            # If not found, try using XPath-like navigation
            if not table:
                logger.info("Table not found by ID, trying alternative selector...")
                main_div = soup.find('div', {'class': 'content'})
                if main_div:
                    tables = main_div.find_all('table')
                    if len(tables) >= 2:
                        table = tables[1]
            
            if not table:
                raise ValueError("Could not find insider trading table on the page")
            
            # Extract table headers
            headers = []
            header_row = table.find('tr', {'class': 'header-row'}) or table.find('tr')
            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    headers.append(th.text.strip())
            
            # Extract table rows
            rows = []
            data_rows = table.find_all('tr')[1:]
            for tr in data_rows:
                row = []
                for td in tr.find_all('td'):
                    visible_text = ''.join(s.strip() for s in td.strings if s.strip())
                    row.append(visible_text)
                if row and len(row) == len(headers):
                    rows.append(row)
            
            df = pd.DataFrame(rows, columns=headers)
            
            if df.empty:
                raise ValueError("No data found in the insider trading table")
            
            # Update cache
            self._cached_data = self.process_insider_data(df)
            self._last_fetch_time = datetime.now()
            
            logger.info(f"Successfully fetched {len(df)} insider trading records")
            return self._cached_data.copy()
            
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return None

    def process_insider_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process and clean the insider trading data."""
        if df is None or df.empty:
            return None

        try:
            # Convert date column to datetime
            df['Date'] = pd.to_datetime(df['Date'])
            
            # Clean up numeric columns
            df['Value ($)'] = df['Value ($)'].str.replace(',', '').astype(float)
            df['Cost'] = df['Cost'].str.replace('$', '').str.replace(',', '').astype(float)
            
            # Add market cap and calculate percentage if API key is available
            if self.av_api_key:
                logger.info("Fetching market cap data...")
                df['Market Cap'] = df['Ticker'].apply(self._get_market_cap)
                df['Trade % of Market Cap'] = (df['Value ($)'] / df['Market Cap']) * 100
            else:
                df['Market Cap'] = 0
                df['Trade % of Market Cap'] = 0
            
            # Sort by value
            df = df.sort_values('Value ($)', ascending=False)
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            return None

    def get_recent_trades(self, days: int = 7, min_value: float = 0) -> pd.DataFrame:
        """Get trades from the last N days."""
        df = self._cached_data
        if df is None:
            df = self.fetch_insider_data()
        
        if df is None or df.empty:
            return None
            
        cutoff_date = datetime.now() - timedelta(days=days)
        mask = (df['Date'] > cutoff_date) & (df['Value ($)'] >= min_value)
        return df[mask]

    def get_trades_by_type(self, transaction_type: Union[str, List[str]]) -> pd.DataFrame:
        """Get trades by transaction type (e.g., 'Buy', 'Sale', 'Option Exercise')."""
        df = self._cached_data
        if df is None:
            df = self.fetch_insider_data()
            
        if df is None or df.empty:
            return None
            
        if isinstance(transaction_type, str):
            transaction_type = [transaction_type]
            
        return df[df['Transaction'].isin(transaction_type)]

    def get_trades_by_market_cap_percent(self, min_percent: float = 0.1) -> pd.DataFrame:
        """Get trades that represent at least min_percent of the company's market cap."""
        if not self.av_api_key:
            logger.warning("Market cap filtering not available without Alpha Vantage API key")
            return None
            
        df = self._cached_data
        if df is None:
            df = self.fetch_insider_data()
            
        if df is None or df.empty:
            return None
            
        return df[df['Trade % of Market Cap'] >= min_percent]

    def filter_trades(self, filters: Dict[str, any]) -> pd.DataFrame:
        """
        Apply multiple filters to the trades data.
        
        filters can include:
        - min_value: minimum transaction value
        - max_days: maximum age of trade in days
        - transaction_types: list of transaction types
        - min_market_cap_percent: minimum percentage of market cap
        - tickers: list of specific tickers to include
        """
        df = self._cached_data
        if df is None:
            df = self.fetch_insider_data()
            
        if df is None or df.empty:
            return None

        # Apply filters
        if 'min_value' in filters:
            df = df[df['Value ($)'] >= filters['min_value']]
            
        if 'max_days' in filters:
            cutoff_date = datetime.now() - timedelta(days=filters['max_days'])
            df = df[df['Date'] > cutoff_date]
            
        if 'transaction_types' in filters:
            df = df[df['Transaction'].isin(filters['transaction_types'])]
            
        if 'min_market_cap_percent' in filters and self.av_api_key:
            df = df[df['Trade % of Market Cap'] >= filters['min_market_cap_percent']]
            
        if 'tickers' in filters:
            df = df[df['Ticker'].isin(filters['tickers'])]
            
        return df

    def print_trade_summary(self, df: pd.DataFrame, title: str = "Trade Summary"):
        """Print a formatted summary of the trades."""
        if df is None or df.empty:
            print(f"\n=== {title} ===")
            print("No trades found matching the criteria.")
            return

        print(f"\n=== {title} ===")
        print(f"Number of trades: {len(df)}")
        print(f"Total value: ${df['Value ($)'].sum():,.2f}")
        print("\nTop 5 trades by value:")
        columns = ['Ticker', 'Owner', 'Relationship', 'Date', 'Transaction', 'Value ($)']
        if self.av_api_key:
            columns.append('Trade % of Market Cap')
        print(df[columns].head().to_string())

def main():
    tracker = InsiderTracker()
    
    # Example usage of different filters
    print("\nFetching and analyzing insider trading data...")
    
    # Get recent large purchases
    filters = {
        # Transaction types: Buy, Sale, Option Exercise, Proposed Sale, 
        'transaction_types': ['Buy'],
        'min_value': 1000000,  # $1M minimum
        'max_days': 10  # Last day
    }
    large_purchases = tracker.filter_trades(filters)
    tracker.print_trade_summary(large_purchases, "Recent Large Purchases (Last 30 Days)")
    
    # Get significant market cap percentage trades
    if tracker.av_api_key:
        filters = {
            'min_market_cap_percent': 1.0,  # At least 1% of market cap
            'max_days': 7  # Last week
        }
        significant_trades = tracker.filter_trades(filters)
        tracker.print_trade_summary(significant_trades, "Significant Market Cap Impact Trades (Last Week)")

if __name__ == "__main__":
    main()
