"""
Generate synthetic stock data for Kronos finetuning.

This script creates realistic synthetic stock data directly without relying on external APIs,
since AKShare and other Chinese stock data providers may be unreachable.

The generated data follows the format expected by Kronos's finetuning pipeline:
- Features: open, high, low, close, vol, amt
- Multi-index format with stock codes as keys and DataFrames as values
"""

import os
import pickle
import pandas as pd
import numpy as np
from tqdm import trange


class SyntheticDataGenerator:
    """Generate synthetic stock data for Kronos finetuning."""

    def __init__(self):
        from config import Config
        self.config = Config()

    def generate_stock_data(self, stock_code, start_date, end_date):
        """Generate synthetic K-line data for a single stock."""
        # Generate date range
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Filter to trading days only (exclude weekends)
        dates = dates[dates.dayofweek < 5]

        np.random.seed(hash(stock_code) % (2**32))
        
        # Generate realistic price movements using geometric Brownian motion
        n_days = len(dates)
        
        # Base price based on stock code pattern (just for variety)
        base_price = 10 + (hash(stock_code) % 100) * 0.1
        
        # Generate returns
        daily_returns = np.random.normal(0.0002, 0.02, n_days)
        
        # Generate close prices from returns
        close_prices = base_price * np.cumprod(1 + daily_returns)
        
        # Generate OHLC data from close prices
        open_prices = np.zeros(n_days)
        high_prices = np.zeros(n_days)
        low_prices = np.zeros(n_days)
        
        open_prices[0] = close_prices[0] * 0.98
        
        for i in range(1, n_days):
            # Open is previous close with some gap
            open_prices[i] = close_prices[i-1] * (1 + np.random.normal(0, 0.005))
            
            # Generate intraday range
            daily_range = abs(np.random.normal(0.015, 0.005))
            high_prices[i] = max(open_prices[i], close_prices[i]) * (1 + daily_range)
            low_prices[i] = min(open_prices[i], close_prices[i]) * (1 - daily_range)
        
        # Generate volume (correlated with price movement)
        price_changes = np.abs(np.diff(close_prices, prepend=close_prices[0]) / close_prices)
        base_volume = 1000000 + (hash(stock_code) % 5000000)
        volumes = base_volume * (1 + price_changes * 100) * np.random.uniform(0.5, 1.5, n_days)
        volumes = volumes.astype(int)
        
        # Generate amount (price * volume)
        amounts = close_prices * volumes / 10000  # Convert to 万元
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'vol': volumes,
            'amt': amounts
        }, index=dates)
        
        # Remove weekend dates from index
        df = df[df.index.dayofweek < 5]
        
        return df

    def generate_all_data(self):
        """Generate train, val, and test data for multiple stocks."""
        print("=" * 60)
        print("Generating Synthetic Kronos Data Files")
        print("=" * 60)

        # Time ranges from config
        train_start, train_end = self.config.train_time_range
        val_start, val_end = self.config.val_time_range
        test_start, test_end = self.config.test_time_range

        # Define stock codes to generate data for
        stock_codes = [
            'sh.600519',  # Kweichow Moutai
            'sh.601318',  # Ping An Insurance
            'sh.600036',  # China Merchants Bank
            'sh.601166',  # Industrial Bank
            'sh.600276',  # Hengrui Medicine
            'sz.000858',  # Wuliangye
            'sz.002415',  # Hikvision
            'sh.600900',  # China Yangtze Power
            'sz.300750',  # CATL (Ningde Times)
            'sh.601398',  # Industrial and Commercial Bank of China
        ]

        print(f"Generating data for {len(stock_codes)} stocks...")

        # Data containers
        train_data, val_data, test_data = {}, {}, {}

        # Generate data for each stock - use enumerate to get index, actual code from list
        successful_stocks = 0
        for idx in trange(len(stock_codes), desc="Generating Stock Data"):
            stock_code = stock_codes[idx]  # Get actual stock code from list
            print(f"  Generating data for {stock_code}...")

            # Generate synthetic stock data
            df = self.generate_stock_data(stock_code, train_start, test_end)

            if len(df) < 100:
                print(f"    Skipping {stock_code}: insufficient data")
                continue

            # Split by time ranges
            train_mask = (df.index >= train_start) & (df.index <= train_end)
            val_mask = (df.index >= val_start) & (df.index <= val_end)
            test_mask = (df.index >= test_start) & (df.index <= test_end)

            train_df = df[train_mask]
            val_df = df[val_mask]
            test_df = df[test_mask]

            # Add to containers using actual stock_code as key
            if len(train_df) > 0:
                train_data[stock_code] = train_df
            if len(val_df) > 0:
                val_data[stock_code] = val_df
            if len(test_df) > 0:
                test_data[stock_code] = test_df

            successful_stocks += 1

        print(f"\nSuccessfully generated data for {successful_stocks} stocks")

        # Save to files
        os.makedirs(self.config.dataset_path, exist_ok=True)

        with open(f"{self.config.dataset_path}/train_data.pkl", 'wb') as f:
            pickle.dump(train_data, f)
        print(f"Saved train_data.pkl ({len(train_data)} stocks)")

        with open(f"{self.config.dataset_path}/val_data.pkl", 'wb') as f:
            pickle.dump(val_data, f)
        print(f"Saved val_data.pkl ({len(val_data)} stocks)")

        with open(f"{self.config.dataset_path}/test_data.pkl", 'wb') as f:
            pickle.dump(test_data, f)
        print(f"Saved test_data.pkl ({len(test_data)} stocks)")

        # Print summary statistics
        print("\n" + "=" * 60)
        print("Data Summary")
        print("=" * 60)

        for name, data in [('train', train_data), ('val', val_data), ('test', test_data)]:
            print(f"\n{name.upper()} Set:")
            if data:
                sample_key = list(data.keys())[0]
                print(f"  Number of stocks: {len(data)}")
                print(f"  Sample stock ({sample_key}):")
                print(f"    Date range: {data[sample_key].index.min().strftime('%Y-%m-%d')} to {data[sample_key].index.max().strftime('%Y-%m-%d')}")
                print(f"    Number of samples: {len(data[sample_key])}")
                print(f"    Features: {list(data[sample_key].columns)}")

        print("\nData generation complete!")


if __name__ == '__main__':
    generator = SyntheticDataGenerator()
    generator.generate_all_data()
