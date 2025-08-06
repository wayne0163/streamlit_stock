import backtrader as bt
from .base import WaySsystemStrategy

class MeanReversionStrategy(WaySsystemStrategy):
    params = (
        ('period', 120),
        ('buy_threshold_factor', 0.2),
    )

    def __init__(self):
        super().__init__()
        self.high_120 = bt.indicators.Highest(self.datahigh, period=self.params.period)
        self.low_120 = bt.indicators.Lowest(self.datalow, period=self.params.period)
        self.range_120 = self.high_120 - self.low_120
        self.buy_condition = (self.range_120 * self.params.buy_threshold_factor) > (self.dataclose - self.low_120)

    def next(self):
        if not self.position:  # 如果没有持仓
            if self.buy_condition[0]:
                self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
                self.buy()
        else:
            # 卖出逻辑可以更复杂，例如使用移动止损或达到某个盈利目标
            # 为简化，我们假设卖出逻辑由回测引擎的通用设置处理
            pass