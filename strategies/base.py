import backtrader as bt
from typing import List, Dict, Any

# 这个文件现在作为策略的公共基类和适配器

class WaySsystemStrategy(bt.Strategy):
    """所有策略的基类，继承自 backtrader.Strategy"""
    def __init__(self):
        # 方便在 next 方法中访问 OHLCV 数据
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.datavolume = self.datas[0].volume

    def log(self, txt, dt=None):
        ''' 策略的日志记录功能 '''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

# --- 适配器函数 ---
def run_strategy_for_screening(strategy_class, data_df) -> List[Dict[str, Any]]:
    """
    适配器函数：用于“选股策略”页面。
    它接收一个为 backtrader 编写的策略和一个数据DataFrame，
    模拟运行策略，并返回其生成的信号。
    """
    cerebro = bt.Cerebro()
    
    # 将数据添加到Cerebro
    data_feed = bt.feeds.PandasData(dataname=data_df)
    cerebro.adddata(data_feed)
    
    # 添加策略
    cerebro.addstrategy(strategy_class)
    
    # 运行策略
    results = cerebro.run()
    
    # 提取信号 (这里我们假设策略在满足条件时会通过某种方式记录信号)
    # 在backtrader中，通常是通过 self.buy() 或 self.sell()。 
    # 为了选股，我们需要策略在__init__中计算指标，并在最后一天检查信号。
    # 这是一个简化的适配器，我们将在具体策略中实现这个逻辑。
    # 此处返回一个空列表，具体逻辑将在策略文件中实现。
    return []