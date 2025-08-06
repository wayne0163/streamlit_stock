import backtrader as bt
from .base import WaySsystemStrategy

class FiveStepStrategy(WaySsystemStrategy):
    params = (
        ('ma_long_period', 240),
        ('ma_short_period_1', 60),
        ('ma_short_period_2', 20),
        ('price_increase_factor', 1.1),
        ('rsi_period_1', 13),
        ('rsi_period_2', 6),
        ('rsi_buy_threshold_1', 50),
        ('rsi_buy_threshold_2', 70),
    )

    def __init__(self):
        super().__init__()
        self.ma240 = bt.indicators.SimpleMovingAverage(self.dataclose, period=self.params.ma_long_period)
        self.ma60 = bt.indicators.SimpleMovingAverage(self.dataclose, period=self.params.ma_short_period_1)
        self.ma20 = bt.indicators.SimpleMovingAverage(self.dataclose, period=self.params.ma_short_period_2)
        self.rsi13 = bt.indicators.RSI_Safe(self.dataclose, period=self.params.rsi_period_1)
        self.rsi6 = bt.indicators.RSI_Safe(self.dataclose, period=self.params.rsi_period_2)
        self.vol_sma = bt.indicators.SimpleMovingAverage(self.datavolume, period=20)

    def next(self):
        # Step 1: MA240 is trending up
        cond1 = self.ma240[0] > self.ma240[-1]
        
        # Step 2: Price is at least 10% higher than 240 days ago
        cond2 = self.dataclose[0] >= self.dataclose[-240] * self.params.price_increase_factor
        
        # Step 3: Either MA60 or MA20 is trending up
        cond3 = (self.ma60[0] > self.ma60[-1]) or (self.ma20[0] > self.ma20[-1])
        
        # Step 4: Volume condition (simplified as it's harder to replicate exactly without more context)
        # We will assume this condition is met for now, or use a simple volume spike.
        cond4 = self.datavolume[0] > self.vol_sma[0] * 1.5

        # Step 5: RSI conditions
        cond5 = (self.rsi13[0] > self.params.rsi_buy_threshold_1) and (self.rsi6[0] > self.params.rsi_buy_threshold_2)

        if not self.position:
            if cond1 and cond2 and cond3 and cond4 and cond5:
                self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
                self.buy()
        else:
            pass