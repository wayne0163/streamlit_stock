import backtrader as bt
import pandas as pd
from typing import Dict, Any, List
import os
from data.database import Database
from strategies.manager import StrategyManager
from config.settings import get_settings
import plotly.graph_objects as go
from plotly.subplots import make_subplots

settings = get_settings()

def create_backtest_plot(results, ts_codes, strategy_name) -> go.Figure:
    """使用Plotly创建交互式回测图表"""
    strat = results[0]
    portfolio_values = pd.Series(strat.analyzers.timereturn.get_analysis())

    # 假设我们主要绘制第一个股票的K线图作为代表
    main_code = ts_codes[0]
    price_data = strat.getdatabyname(main_code)
    
    # 从 backtrader 的 line buffer 安全地提取数据
    dates = [bt.num2date(x) for x in price_data.datetime.array]
    df_price = pd.DataFrame({
        'open': price_data.open.array,
        'high': price_data.high.array,
        'low': price_data.low.array,
        'close': price_data.close.array,
        'volume': price_data.volume.array,
    }, index=pd.to_datetime(dates))

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        subplot_titles=(f'{main_code} Candlestick', 'Portfolio Value', 'Volume'),
                        row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df_price.index, open=df_price['open'], high=df_price['high'],
                                 low=df_price['low'], close=df_price['close'], name='Price'),
                  row=1, col=1)

    # 提取并绘制交易点
    trades = strat.analyzers.trade_analyzer.get_analysis()
    buy_dates, sell_dates = [], []
    if trades and trades.get('total', {}).get('total', 0) > 0:
        for t in trades.values():
            if isinstance(t, dict) and 'trades' in t:
                for trade in t['trades']:
                    if trade['pnl'] != 0: # 这是一个实际的交易
                        trade_date = bt.num2date(trade['dtopen'])
                        if trade['size'] > 0:
                            buy_dates.append(trade_date)
                        else:
                            sell_dates.append(trade_date)

    # 确保交易日期在价格数据范围内
    valid_buy_dates = [d for d in buy_dates if d in df_price.index]
    valid_sell_dates = [d for d in sell_dates if d in df_price.index]

    if valid_buy_dates:
        fig.add_trace(go.Scatter(x=valid_buy_dates, y=df_price.loc[valid_buy_dates, 'low'] * 0.98, mode='markers', name='Buy Signal',
                                 marker=dict(symbol='triangle-up', color='green', size=10)),
                      row=1, col=1)
    if valid_sell_dates:
        fig.add_trace(go.Scatter(x=valid_sell_dates, y=df_price.loc[valid_sell_dates, 'high'] * 1.02, mode='markers', name='Sell Signal',
                                 marker=dict(symbol='triangle-down', color='red', size=10)),
                      row=1, col=1)

    fig.add_trace(go.Scatter(x=portfolio_values.index, y=portfolio_values.values, name='Portfolio Value'),
                  row=2, col=1)

    fig.add_trace(go.Bar(x=df_price.index, y=df_price['volume'], name='Volume'),
                  row=3, col=1)

    fig.update_layout(height=800, title_text=f"Backtest Results for Strategy: {strategy_name}",
                      xaxis_rangeslider_visible=False)
    return fig

def run_backtest(strategy_name: str, ts_codes: List[str], start_date: str, end_date: str, 
                 initial_capital: float, max_positions: int) -> Dict[str, Any]:
    cerebro = bt.Cerebro()
    
    strategy_manager = StrategyManager(Database())
    strategy_class = strategy_manager.get_strategy_class(strategy_name)
    if not strategy_class:
        raise ValueError(f"策略 '{strategy_name}' 未找到")
    cerebro.addstrategy(strategy_class)

    db = Database()
    for ts_code in ts_codes:
        query = "SELECT date, open, high, low, close, volume FROM daily_price WHERE ts_code = ? AND date BETWEEN ? AND ? ORDER BY date"
        df = pd.DataFrame(db.fetch_all(query, (ts_code, start_date, end_date)))
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            data_feed = bt.feeds.PandasData(dataname=df)
            cerebro.adddata(data_feed, name=ts_code)

    cerebro.broker.setcash(initial_capital)
    cerebro.broker.setcommission(commission=settings.BACKTEST_FEE_RATE)
    sizers_perc = 95 / max_positions
    cerebro.addsizer(bt.sizers.PercentSizer, percents=sizers_perc)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe_ratio')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')

    print("--- 开始运行 Backtrader 回测 ---")
    results = cerebro.run()
    print("--- 回测结束 ---")

    thestrat = results[0]
    trade_analysis = thestrat.analyzers.trade_analyzer.get_analysis()
    
    metrics = {
        'total_return': thestrat.analyzers.returns.get_analysis().get('rtot', 0) * 100,
        'annual_return': thestrat.analyzers.returns.get_analysis().get('rann', 0) * 100,
        'sharpe_ratio': 0,
        'max_drawdown': thestrat.analyzers.drawdown.get_analysis().get('max', {}).get('drawdown', 0),
        'total_trades': trade_analysis.get('total', {}).get('total', 0),
        'win_rate': 0,
    }
    
    # 安全获取夏普比率
    sharpe_analysis = thestrat.analyzers.sharpe_ratio.get_analysis()
    if sharpe_analysis is not None:
        metrics['sharpe_ratio'] = sharpe_analysis.get('sharperatio', 0)
    
    total_trades = trade_analysis.get('total', {}).get('total', 0)
    if total_trades > 0:
        metrics['win_rate'] = (trade_analysis.get('won', {}).get('total', 0) / total_trades) * 100

    plot_figure = create_backtest_plot(results, ts_codes, strategy_name)

    return {
        'metrics': metrics,
        'plot_figure': plot_figure
    }