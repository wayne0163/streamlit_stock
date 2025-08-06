import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from data.database import Database

class PortfolioManager:
    def __init__(self, db: Database, portfolio_name: str = 'default'):
        self.db = db
        self.portfolio_name = portfolio_name
        self.cash: Optional[float] = None
        self.positions: Dict[str, Dict[str, float]] = {}
        self.load_portfolio()

    def is_initialized(self) -> bool:
        return self.cash is not None

    def initialize_cash(self, amount: float):
        self.cash = amount
        self.save_portfolio()

    def reset_portfolio(self):
        self.db.execute("DELETE FROM trades WHERE portfolio_name = ?", (self.portfolio_name,))
        self.db.execute("DELETE FROM portfolio WHERE portfolio_name = ?", (self.portfolio_name,))
        self.cash = None
        self.positions = {}
        print(f"Portfolio '{self.portfolio_name}' has been reset.")

    def load_portfolio(self):
        rows = self.db.fetch_all("SELECT ts_code, qty, cost FROM portfolio WHERE portfolio_name = ?", (self.portfolio_name,))
        cash_found = False
        self.positions = {}
        for row in rows:
            if row['ts_code'] == 'CASH':
                self.cash = row['cost']
                cash_found = True
            else:
                self.positions[row['ts_code']] = {'qty': row['qty'], 'cost': row['cost']}
        if not cash_found:
            self.cash = None

    def save_portfolio(self):
        if not self.is_initialized():
            return
        self.db.execute("DELETE FROM portfolio WHERE portfolio_name = ?", (self.portfolio_name,))
        data_to_insert = [(self.portfolio_name, ts_code, pos['qty'], pos['cost']) for ts_code, pos in self.positions.items()]
        data_to_insert.append((self.portfolio_name, 'CASH', 1, self.cash))
        self.db.executemany("INSERT INTO portfolio (portfolio_name, ts_code, qty, cost) VALUES (?, ?, ?, ?)", data_to_insert)

    def update_cash(self, amount: float):
        if not self.is_initialized():
            raise ValueError("Portfolio not initialized.")
        if self.cash + amount < 0:
            raise ValueError(f"Not enough cash to withdraw.")
        self.cash += amount
        self.save_portfolio()

    def add_trade(self, side: str, ts_code: str, price: float, qty: float, fee: float = 0, date: str = None):
        if not self.is_initialized():
            raise ValueError("Portfolio not initialized.")
        date = date or datetime.now().strftime('%Y%m%d')
        side = side.lower()
        if side == 'buy':
            cost = price * qty + fee
            if self.cash < cost:
                raise ValueError("Not enough cash.")
            self.cash -= cost
            if ts_code in self.positions:
                current_qty = self.positions[ts_code]['qty']
                current_cost = self.positions[ts_code]['cost']
                new_qty = current_qty + qty
                new_avg_cost = (current_qty * current_cost + price * qty) / new_qty
                self.positions[ts_code].update({'qty': new_qty, 'cost': new_avg_cost})
            else:
                self.positions[ts_code] = {'qty': qty, 'cost': price}
            
            stock_info = self.db.fetch_one("SELECT name FROM stocks WHERE ts_code = ?", (ts_code,))
            if stock_info:
                self.db.execute("INSERT OR IGNORE INTO watchlist (ts_code, name, add_date, in_pool) VALUES (?, ?, ?, ?)", 
                                (ts_code, stock_info['name'], datetime.now().strftime('%Y-%m-%d'), 0))
                print(f"已自动将 {ts_code} 添加到自选股列表。")

        elif side == 'sell':
            if ts_code not in self.positions or self.positions[ts_code]['qty'] < qty:
                raise ValueError("Not enough shares to sell.")
            revenue = price * qty - fee
            self.cash += revenue
            self.positions[ts_code]['qty'] -= qty
            if self.positions[ts_code]['qty'] == 0:
                del self.positions[ts_code]
        self.db.execute("INSERT INTO trades (date, portfolio_name, ts_code, side, price, qty, fee) VALUES (?, ?, ?, ?, ?, ?, ?)", (date, self.portfolio_name, ts_code, side, price, qty, fee))
        self.save_portfolio()

    def get_trade_history(self, ts_code: str = None, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM trades WHERE portfolio_name = ?"
        params = [self.portfolio_name]
        if ts_code:
            query += " AND ts_code = ?"
            params.append(ts_code)
        query += " ORDER BY date DESC"
        return self.db.fetch_all(query, tuple(params))

    def generate_portfolio_report(self) -> Dict[str, Any]:
        if not self.is_initialized():
            return {'portfolio_name': self.portfolio_name, 'cash': 0, 'positions': [], 'summary': {'total_value': 0, 'position_count': 0, 'investment_value': 0}}

        report = {'portfolio_name': self.portfolio_name, 'cash': self.cash, 'positions': [], 'summary': {}}
        if not self.positions:
            report['summary'] = {'total_value': self.cash, 'position_count': 0, 'investment_value': 0}
            return report

        ts_codes = list(self.positions.keys())
        placeholders = ','.join('?' for _ in ts_codes)
        query = f"""SELECT p.ts_code, s.name, p.close as current_price
                   FROM daily_price p
                   JOIN (
                       SELECT ts_code, MAX(date) as max_date 
                       FROM daily_price 
                       WHERE ts_code IN ({placeholders}) 
                       GROUP BY ts_code
                   ) AS latest ON p.ts_code = latest.ts_code AND p.date = latest.max_date
                   LEFT JOIN stocks s ON p.ts_code = s.ts_code"""
        
        market_data_rows = self.db.fetch_all(query, tuple(ts_codes))
        market_data = {row['ts_code']: {'name': row['name'], 'current_price': row['current_price']} for row in market_data_rows}

        total_investment_value = 0
        for ts_code, pos in self.positions.items():
            qty = pos['qty']
            market_info = market_data.get(ts_code)
            
            if market_info:
                current_price = market_info.get('current_price') if market_info.get('current_price') is not None else 0
                name = market_info.get('name', 'N/A')
            else:
                current_price = 0
                stock_details = self.db.fetch_one("SELECT name FROM stocks WHERE ts_code = ?", (ts_code,))
                name = stock_details['name'] if stock_details else 'N/A'
            
            market_value = qty * current_price
            total_investment_value += market_value
            
            report['positions'].append({
                'ts_code': ts_code, 
                'name': name, 
                'qty': qty, 
                'cost_price': pos['cost'], 
                'current_price': current_price, 
                'market_value': market_value, 
                'pnl': (current_price - pos['cost']) * qty if current_price > 0 else 0
            })

        total_portfolio_value = self.cash + total_investment_value
        report['summary'] = {'total_value': total_portfolio_value, 'investment_value': total_investment_value, 'position_count': len(self.positions)}
        return report