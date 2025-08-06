import backtrader as bt
from .base import WaySsystemStrategy

class TrendBreakoutStrategy(WaySsystemStrategy):
    params = (
        ('period', 240),
        ('buy_threshold_factor', 0.9),
    )

    def __init__(self):
        super().__init__()
        self.high_240 = bt.indicators.Highest(self.datahigh, period=self.params.period)
        self.low_240 = bt.indicators.Lowest(self.datalow, period=self.params.period)
        self.range_240 = self.high_240 - self.low_240
        self.buy_condition = (self.range_240 * self.params.buy_threshold_factor) < (self.dataclose - self.low_240)

    def next(self):
        if not self.position:
            if self.buy_condition[0]:
                self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
                self.buy()
        else:
            pass