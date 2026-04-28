"""
Generate train/val/test data files using AKShare for China A-share market.

This script fetches stock data from AKShare and saves it in the format expected
by Kronos's finetuning pipeline.
"""

import os
import pickle
import pandas as pd
import numpy as np
from tqdm import trange


class AKShareDataGenerator:
    """Generate Kronos-compatible data files using AKShare."""

    def __init__(self):
        import akshare as ak
        self.ak = ak
        from config import Config
        self.config = Config()

    def get_stock_list(self):
        """Get a list of stocks to fetch data for."""
        # Use predefined list with proper sh./sz. prefix format
        print("Using predefined stock list...")
        return ['sh.600519', 'sh.601318', 'sh.600036', 'sh.601166', 'sh.600276',
                'sz.000001', 'sz.000002', 'sz.002415', 'sz.300750', 'sh.000858']

    def fetch_stock_history(self, stock_code):
        """Fetch historical K-line data for a single stock using AKShare."""
        try:
            # Extract just the code part (remove sh. or sz. prefix)
            clean_code = str(stock_code).replace('sh.', '').replace('sz.', '')

            # Get daily historical data with forward adjustment (前复权)
            df = self.ak.stock_zh_a_hist(
                symbol=clean_code,
                period="daily",
                adjust="qfq"  # forward adjusted price
            )

            if df is None or len(df) == 0:
                return None

            # Rename columns to match expected format
            df = df.rename(columns={
                '日期': 'datetime',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'vol',
                '成交额': 'amt'
            })

            # Convert datetime and set as index
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            df = df.sort_index()

            # Ensure all required columns exist
            for col in ['open', 'high', 'low', 'close', 'vol', 'amt']:
                if col not in df.columns:
                    df[col] = 0.0

            # Select only required features
            df = df[['open', 'high', 'low', 'close', 'vol', 'amt']]

            return df

        except Exception as e:
            print(f"Error fetching {stock_code}: {e}")
            return None

    def generate_data(self):
        """Generate train, val, and test data files."""
        print("=" * 60)
        print("Generating Kronos Data Files using AKShare")
        print("=" * 60)

        # Get stock list
        stock_codes = self.get_stock_list()
        print(f"Fetching data for {len(stock_codes)} stocks...")

        # Time ranges from config
        train_start, train_end = self.config.train_time_range
        val_start, val_end = self.config.val_time_range
        test_start, test_end = self.config.test_time_range

        # Data containers
        train_data, val_data, test_data = {}, {}, {}

        # Fetch data for each stock
        successful_stocks = 0
        for stock_code in trange(len(stock_codes), desc="Fetching Stock Data"):
            df = self.fetch_stock_history(stock_code)

            if df is None or len(df) < 100:
                print(f"  Skipping {stock_code}: insufficient data")
                continue

            # Split by time ranges
            train_mask = (df.index >= train_start) & (df.index <= train_end)
            val_mask = (df.index >= val_start) & (df.index <= val_end)
            test_mask = (df.index >= test_start) & (df.index <= test_end)

            train_df = df[train_mask]
            val_df = df[val_mask]
            test_df = df[test_mask]

            # Use stock_code directly (already has sh./sz. prefix)
            if len(train_df) > 0:
                train_data[stock_code] = train_df
            if len(val_df) > 0:
                val_data[stock_code] = val_df
            if len(test_df) > 0:
                test_data[stock_code] = test_df

            successful_stocks += 1

        print(f"\nSuccessfully fetched data for {successful_stocks} stocks")

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

        print("\nData generation complete!")


if __name__ == '__main__':
    generator = AKShareDataGenerator()
    generator.generate_data()
