# this is made for learning purpose, until I can find a good strategy.
# this is going to trade with paper money.

from ib_async import *
import random
import time
import csv
from datetime import datetime

util.startLoop()
ib = IB()
ib.connect(port=4002, clientId=0)


class RSITradingBot:
    def __init__(self):
        self.apple_contract = Stock('AAPL', 'NASDAQ', 'USD')
        self.quantity = 100

        self.rsi_period = 14
        self.long_trigger = 32
        self.long_entry = 34.8
        self.short_trigger = 68
        self.short_entry = 71.7
        self.exit_min = 48
        self.exit_max = 52

        self.position = 0
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_rsi = 0.0
        self.rsi_values = []
        self.trade_history = []

        self.init_log_files()

        self.setup_market_data()

        # Print header
        print("\n")
        print("DELAYED DATA RSI BOT WITH TRADE LOGGING")
        print(f"{'Time':8} | {'Price':7} | {'RSI':6} | {'Position':8}")
        print("-" * 45)

    def init_log_files(self):
        with open('trade_log.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow([
                    'Entry Time', 'Exit Time', 'Direction',
                    'Entry Price', 'Exit Price', 'Quantity',
                    'Profit', 'Entry RSI', 'Exit RSI', 'Duration (min)'
                ])

        with open('daily_summary.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0:  # Write header if file is empty
                writer.writerow([
                    'Date', 'Total Trades', 'Long Trades', 'Short Trades',
                    'Total Profit', 'Avg Profit/Trade', 'Winning Trades',
                    'Losing Trades'
                ])

    def setup_market_data(self):
        # Use delayed market data (no subscription needed)
        ib.reqMarketDataType(3)

        # Get historical data
        self.bars = ib.reqHistoricalData(
            contract=self.apple_contract,
            endDateTime='',
            durationStr='1 D',  # 1 day of data
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1,
            keepUpToDate=True
        )
        self.bars.updateEvent += self.on_bar_update
        print("Market data initialized with delayed feed")

    def calculate_rsi(self, prices):
        if len(prices) < self.rsi_period + 1:
            return 50.0

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]

        avg_gain = sum(gains[:self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[:self.rsi_period]) / self.rsi_period

        for i in range(self.rsi_period, len(deltas)):
            avg_gain = (avg_gain * (self.rsi_period - 1) + gains[i]) / self.rsi_period
            avg_loss = (avg_loss * (self.rsi_period - 1) + losses[i]) / self.rsi_period

        if avg_loss == 0:
            return 100.0
        return 100 - (100 / (1 + (avg_gain / avg_loss)))

    def on_bar_update(self, bars, has_new_bar):
        if not has_new_bar or len(bars) < 1:
            return

        try:
            current_price = bars[-1].close
            current_time = datetime.now().strftime('%H:%M:%S')

            # Calculate RSI
            closes = [bar.close for bar in bars]
            current_rsi = self.calculate_rsi(closes)
            self.rsi_values.append(current_rsi)

            # Print status
            position_str = {0: "Flat", 1: "Long", -1: "Short"}[self.position]
            print(f"{current_time} | {current_price:7.2f} | {current_rsi:6.2f} | {position_str:8}")

            # Check trading conditions
            self.check_trading_conditions(current_rsi, current_price)

            # Update daily summary at market close
            if datetime.now().hour == 16 and datetime.now().minute == 0:
                self.update_daily_summary()

        except Exception as e:
            print(f"Data error: {str(e)}")

    def check_trading_conditions(self, current_rsi, current_price):
        # Exit condition (random between 48-52)
        if self.position != 0:
            exit_rsi = random.uniform(self.exit_min, self.exit_max)
            if (self.position == 1 and current_rsi >= exit_rsi) or \
                    (self.position == -1 and current_rsi <= exit_rsi):
                self.exit_position(current_rsi, current_price)
                return

        # Entry conditions (only if flat)
        if self.position == 0 and len(self.rsi_values) >= 2:
            prev_rsi = self.rsi_values[-2]

            # Long entry
            if prev_rsi < self.long_trigger and current_rsi >= self.long_entry:
                self.enter_long(current_rsi, current_price)

            # Short entry
            elif prev_rsi > self.short_trigger and current_rsi >= self.short_entry:
                self.enter_short(current_rsi, current_price)

    def enter_long(self, entry_rsi, entry_price):
        print(f"\nENTER LONG: Price={entry_price:.2f}, RSI={entry_rsi:.2f}")

        try:
            order = MarketOrder('BUY', self.quantity)
            trade = ib.placeOrder(self.apple_contract, order)

            self.position = 1
            self.entry_price = trade.orderStatus.avgFillPrice
            self.entry_time = datetime.now()
            self.entry_rsi = entry_rsi

            # Log trade entry
            self.trade_history.append({
                'entry_time': self.entry_time,
                'direction': 'LONG',
                'entry_price': self.entry_price,
                'quantity': self.quantity,
                'entry_rsi': entry_rsi
            })
        except Exception as e:
            print(f"Order error: {str(e)}")

    def enter_short(self, entry_rsi, entry_price):
        print(f"\nENTER SHORT: Price={entry_price:.2f}, RSI={entry_rsi:.2f}")

        try:
            order = MarketOrder('SELL', self.quantity)
            trade = ib.placeOrder(self.apple_contract, order)

            self.position = -1
            self.entry_price = trade.orderStatus.avgFillPrice
            self.entry_time = datetime.now()
            self.entry_rsi = entry_rsi

            self.trade_history.append({
                'entry_time': self.entry_time,
                'direction': 'SHORT',
                'entry_price': self.entry_price,
                'quantity': self.quantity,
                'entry_rsi': entry_rsi
            })
        except Exception as e:
            print(f"Order error: {str(e)}")

    def exit_position(self, exit_rsi, exit_price):
        exit_time = datetime.now()
        duration = (exit_time - self.entry_time).total_seconds() / 60  # minutes

        try:
            action = 'SELL' if self.position == 1 else 'BUY'
            print(f"\nEXIT {action}: Price={exit_price:.2f}, RSI={exit_rsi:.2f}")

            order = MarketOrder(action, self.quantity)
            trade = ib.placeOrder(self.apple_contract, order)
            exit_price = trade.orderStatus.avgFillPrice

            # Calculate P&L
            pnl = (exit_price - self.entry_price) * self.quantity * self.position
            print(f"TRADE RESULT: ${pnl:+.2f}")

            # Update trade record
            current_trade = self.trade_history[-1]
            current_trade.update({
                'exit_time': exit_time,
                'exit_price': exit_price,
                'exit_rsi': exit_rsi,
                'profit': pnl,
                'duration': duration
            })

            # Log complete trade
            self.log_trade(current_trade)

            # Reset position
            self.position = 0
            self.entry_price = 0.0
            self.entry_time = None

        except Exception as e:
            print(f"Order error: {str(e)}")

    def log_trade(self, trade):
        with open('trade_log.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade['entry_time'].strftime('%Y-%m-%d %H:%M:%S'),
                trade['exit_time'].strftime('%Y-%m-%d %H:%M:%S'),
                trade['direction'],
                trade['entry_price'],
                trade['exit_price'],
                trade['quantity'],
                trade['profit'],
                trade['entry_rsi'],
                trade['exit_rsi'],
                f"{trade['duration']:.2f}"
            ])

    def update_daily_summary(self):
        today = datetime.now().strftime('%Y-%m-%d')
        today_trades = [t for t in self.trade_history
                        if t['exit_time'].strftime('%Y-%m-%d') == today]

        if not today_trades:
            return

        total_trades = len(today_trades)
        long_trades = sum(1 for t in today_trades if t['direction'] == 'LONG')
        short_trades = total_trades - long_trades
        total_profit = sum(t['profit'] for t in today_trades)
        avg_profit = total_profit / total_trades if total_trades else 0
        winning_trades = sum(1 for t in today_trades if t['profit'] > 0)
        losing_trades = total_trades - winning_trades

        with open('daily_summary.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                today,
                total_trades,
                long_trades,
                short_trades,
                f"{total_profit:.2f}",
                f"{avg_profit:.2f}",
                winning_trades,
                losing_trades
            ])

        print(f"\nDaily Summary for {today}:")
        print(f"Trades: {total_trades} (Long: {long_trades}, Short: {short_trades})")
        print(f"Total Profit: ${total_profit:.2f}")
        print(f"Win Rate: {winning_trades}/{total_trades}")


if __name__ == "__main__":
    print("Starting AAPL RSI Bot with Trade Logging")
    print("Using free delayed market data (15-20 min delay)")

    try:
        bot = RSITradingBot()
        while True:
            ib.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot...")
        bot.update_daily_summary()
    finally:
        ib.disconnect()