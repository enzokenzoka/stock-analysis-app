# app.py - Your main application file (updated for deployment)
import os
import requests
from flask import Flask, render_template_string, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import webbrowser
from sklearn.preprocessing import StandardScaler
import warnings
from advanced_analytics import AdvancedAnalyzer, NewsAnalyzer, SectorAnalyzer, EarningsAnalyzer
import sqlite3
from datetime import datetime, timedelta
import uuid
import json
warnings.filterwarnings('ignore')


app = Flask(__name__)


# ===== NEW: PORTFOLIO DATABASE FUNCTIONS =====

def init_portfolio_database():
    """Initialize portfolio and tracking databases"""
    conn = sqlite3.connect('portfolio.db')
    cursor = conn.cursor()
    
    # User portfolios table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default_user',
            symbol TEXT,
            added_date TEXT,
            added_price REAL,
            current_price REAL,
            signal_when_added TEXT,
            confidence_when_added REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, symbol)
        )
    ''')
    
    # Prediction tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prediction_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            prediction_date TEXT,
            signal TEXT,
            confidence REAL,
            price_when_predicted REAL,
            target_price_1week REAL,
            target_price_1month REAL,
            target_price_3month REAL,
            actual_price_1week REAL,
            actual_price_1month REAL,
            actual_price_3month REAL,
            accuracy_1week REAL,
            accuracy_1month REAL,
            accuracy_3month REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

class PortfolioManager:
    def __init__(self):
        self.db_name = 'portfolio.db'
        init_portfolio_database()
    
    def add_to_portfolio(self, symbol, current_price, signal, confidence):
        """Add stock to user portfolio"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute('''
                SELECT id FROM user_portfolios 
                WHERE user_id = ? AND symbol = ?
            ''', ('default_user', symbol))
            
            if cursor.fetchone():
                conn.close()
                return {"success": False, "message": f"{symbol} already in portfolio"}
            
            # Add to portfolio
            cursor.execute('''
                INSERT INTO user_portfolios 
                (user_id, symbol, added_date, added_price, current_price, signal_when_added, confidence_when_added)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('default_user', symbol, datetime.now().strftime('%Y-%m-%d'), 
                  current_price, current_price, signal, confidence))
            
            conn.commit()
            conn.close()
            return {"success": True, "message": f"{symbol} added to portfolio"}
            
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def remove_from_portfolio(self, symbol):
        """Remove stock from portfolio"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM user_portfolios 
                WHERE user_id = ? AND symbol = ?
            ''', ('default_user', symbol))
            
            conn.commit()
            conn.close()
            return {"success": True, "message": f"{symbol} removed from portfolio"}
            
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def get_portfolio(self):
        """Get user's portfolio with current analysis"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT symbol, added_date, added_price, current_price, 
                       signal_when_added, confidence_when_added, created_at
                FROM user_portfolios 
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', ('default_user',))
            
            portfolio_data = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            portfolio = []
            for row in portfolio_data:
                portfolio.append({
                    'symbol': row[0],
                    'added_date': row[1],
                    'added_price': row[2],
                    'current_price': row[3],
                    'signal_when_added': row[4],
                    'confidence_when_added': row[5],
                    'created_at': row[6]
                })
            
            return portfolio
            
        except Exception as e:
            print(f"Error getting portfolio: {e}")
            return []
    
    def update_portfolio_prices(self, analyzer):
        """Update current prices for portfolio stocks"""
        try:
            portfolio = self.get_portfolio()
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            for stock in portfolio:
                # Get current analysis
                current_analysis = analyzer.analyze_stock(stock['symbol'])
                if current_analysis:
                    cursor.execute('''
                        UPDATE user_portfolios 
                        SET current_price = ?
                        WHERE user_id = ? AND symbol = ?
                    ''', (current_analysis['current_price'], 'default_user', stock['symbol']))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error updating portfolio prices: {e}")
            return False
    
    def save_prediction(self, symbol, analysis):
        """Save prediction for tracking accuracy"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Extract prediction data
            prob_ranges = analysis.get('probability_ranges', {})
            
            cursor.execute('''
                INSERT INTO prediction_tracking 
                (symbol, prediction_date, signal, confidence, price_when_predicted, 
                 target_price_1week, target_price_1month, target_price_3month)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                datetime.now().strftime('%Y-%m-%d'),
                analysis['signal'],
                analysis['confidence'],
                analysis['current_price'],
                prob_ranges.get('1_week', {}).get('expected_price', 0),
                prob_ranges.get('1_month', {}).get('expected_price', 0),
                prob_ranges.get('3_months', {}).get('expected_price', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error saving prediction: {e}")
            return False
    
    def get_portfolio_performance(self):
        """Calculate portfolio performance metrics"""
        try:
            portfolio = self.get_portfolio()
            if not portfolio:
                return {"total_value": 0, "total_gain": 0, "total_gain_percent": 0, "stocks": []}
            
            total_invested = 0
            total_current = 0
            performance_data = []
            
            for stock in portfolio:
                added_price = stock['added_price']
                current_price = stock['current_price']
                gain = current_price - added_price
                gain_percent = (gain / added_price) * 100 if added_price > 0 else 0
                
                total_invested += added_price
                total_current += current_price
                
                performance_data.append({
                    'symbol': stock['symbol'],
                    'added_price': added_price,
                    'current_price': current_price,
                    'gain': gain,
                    'gain_percent': gain_percent,
                    'signal_when_added': stock['signal_when_added'],
                    'confidence_when_added': stock['confidence_when_added'],
                    'added_date': stock['added_date']
                })
            
            total_gain = total_current - total_invested
            total_gain_percent = (total_gain / total_invested) * 100 if total_invested > 0 else 0
            
            return {
                "total_invested": total_invested,
                "total_current": total_current,
                "total_gain": total_gain,
                "total_gain_percent": total_gain_percent,
                "stocks": performance_data
            }
            
        except Exception as e:
            print(f"Error calculating portfolio performance: {e}")
            return {"total_value": 0, "total_gain": 0, "total_gain_percent": 0, "stocks": []}

# ===== NEW: PORTFOLIO ROUTES =====

# Create portfolio manager instance
portfolio_manager = PortfolioManager()

# ===== DYNAMIC STOCK LIST MANAGEMENT =====

class StockListManager:
    def __init__(self):
        self.db_name = 'portfolio.db'
        self.init_watchlist_table()
        self.init_default_stocks()
    
    def init_watchlist_table(self):
        """Initialize watchlist table"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE,
                    company_name TEXT,
                    sector TEXT,
                    market_cap TEXT,
                    added_by_user BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Watchlist table created")
            
        except Exception as e:
            print(f"❌ Error creating watchlist table: {e}")
    
    def init_default_stocks(self):
        """Initialize with default popular stocks if empty"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Check if watchlist is empty
            cursor.execute("SELECT COUNT(*) FROM watchlist")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Add default popular stocks
                default_stocks = [
                    ('AAPL', 'Apple Inc.', 'Technology', 'Large Cap'),
                    ('GOOGL', 'Alphabet Inc.', 'Technology', 'Large Cap'),
                    ('MSFT', 'Microsoft Corporation', 'Technology', 'Large Cap'),
                    ('TSLA', 'Tesla Inc.', 'Automotive', 'Large Cap'),
                    ('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 'Large Cap'),
                    ('META', 'Meta Platforms Inc.', 'Technology', 'Large Cap'),
                    ('NVDA', 'NVIDIA Corporation', 'Technology', 'Large Cap'),
                    ('NFLX', 'Netflix Inc.', 'Communication Services', 'Large Cap'),
                    ('UBER', 'Uber Technologies Inc.', 'Technology', 'Large Cap'),
                    ('SNAP', 'Snap Inc.', 'Communication Services', 'Mid Cap'),
                    ('ZOOM', 'Zoom Video Communications', 'Technology', 'Mid Cap'),
                    ('PLTR', 'Palantir Technologies Inc.', 'Technology', 'Mid Cap'),
                    ('COIN', 'Coinbase Global Inc.', 'Financial Services', 'Mid Cap'),
                    ('RBLX', 'Roblox Corporation', 'Communication Services', 'Mid Cap'),
                    ('SHOP', 'Shopify Inc.', 'Technology', 'Large Cap'),
                    ('SQ', 'Block Inc.', 'Technology', 'Mid Cap'),
                    ('PYPL', 'PayPal Holdings Inc.', 'Financial Services', 'Large Cap'),
                    ('ADBE', 'Adobe Inc.', 'Technology', 'Large Cap'),
                    ('CRM', 'Salesforce Inc.', 'Technology', 'Large Cap'),
                    ('SPOT', 'Spotify Technology SA', 'Communication Services', 'Mid Cap')
                ]
                
                for symbol, name, sector, market_cap in default_stocks:
                    cursor.execute('''
                        INSERT OR IGNORE INTO watchlist 
                        (symbol, company_name, sector, market_cap, added_by_user, is_active)
                        VALUES (?, ?, ?, ?, FALSE, TRUE)
                    ''', (symbol, name, sector, market_cap))
                
                conn.commit()
                print(f"✅ Added {len(default_stocks)} default stocks to watchlist")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error initializing default stocks: {e}")
    
    def get_active_stocks(self):
        """Get list of active stocks for analysis"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT symbol FROM watchlist 
                WHERE is_active = TRUE 
                ORDER BY symbol
            ''')
            
            stocks = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return stocks
            
        except Exception as e:
            print(f"❌ Error getting active stocks: {e}")
            return ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']  # Fallback
    
    def get_watchlist_details(self):
        """Get detailed watchlist with company info"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT symbol, company_name, sector, market_cap, is_active, added_by_user, created_at
                FROM watchlist 
                ORDER BY symbol
            ''')
            
            watchlist = []
            for row in cursor.fetchall():
                watchlist.append({
                    'symbol': row[0],
                    'company_name': row[1],
                    'sector': row[2],
                    'market_cap': row[3],
                    'is_active': bool(row[4]),
                    'added_by_user': bool(row[5]),
                    'created_at': row[6]
                })
            
            conn.close()
            return watchlist
            
        except Exception as e:
            print(f"❌ Error getting watchlist details: {e}")
            return []
    
    def add_stock_to_watchlist(self, symbol, company_name=None):
        """Add new stock to watchlist"""
        try:
            symbol = symbol.upper().strip()
            
            # Validate stock symbol using yfinance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or 'symbol' not in info:
                return {"success": False, "message": f"Invalid stock symbol: {symbol}"}
            
            # Get company info if not provided
            if not company_name:
                company_name = info.get('longName', info.get('shortName', symbol))
            
            sector = info.get('sector', 'Unknown')
            market_cap = info.get('marketCap', 0)
            
            # Determine market cap category
            if market_cap > 200_000_000_000:
                market_cap_category = 'Large Cap'
            elif market_cap > 10_000_000_000:
                market_cap_category = 'Mid Cap'
            elif market_cap > 2_000_000_000:
                market_cap_category = 'Small Cap'
            else:
                market_cap_category = 'Micro Cap'
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO watchlist 
                (symbol, company_name, sector, market_cap, added_by_user, is_active)
                VALUES (?, ?, ?, ?, TRUE, TRUE)
            ''', (symbol, company_name, sector, market_cap_category))
            
            conn.commit()
            conn.close()
            
            return {
                "success": True, 
                "message": f"Added {symbol} ({company_name}) to watchlist",
                "details": {
                    "symbol": symbol,
                    "company_name": company_name,
                    "sector": sector,
                    "market_cap": market_cap_category
                }
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error adding {symbol}: {str(e)}"}
    
    def remove_stock_from_watchlist(self, symbol):
        """Remove stock from watchlist"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM watchlist WHERE symbol = ?', (symbol.upper(),))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                return {"success": True, "message": f"Removed {symbol} from watchlist"}
            else:
                conn.close()
                return {"success": False, "message": f"{symbol} not found in watchlist"}
            
        except Exception as e:
            return {"success": False, "message": f"Error removing {symbol}: {str(e)}"}
    
    def toggle_stock_active(self, symbol, is_active):
        """Enable/disable stock in analysis without removing from watchlist"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE watchlist 
                SET is_active = ? 
                WHERE symbol = ?
            ''', (is_active, symbol.upper()))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                status = "enabled" if is_active else "disabled"
                return {"success": True, "message": f"{symbol} {status} for analysis"}
            else:
                conn.close()
                return {"success": False, "message": f"{symbol} not found in watchlist"}
            
        except Exception as e:
            return {"success": False, "message": f"Error updating {symbol}: {str(e)}"}

# Create stock list manager instance
stock_list_manager = StockListManager()


@app.route('/watchlist')
def watchlist_page():
    """Watchlist management page"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>📋 Stock Watchlist - Manage Your Stocks</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        
        .nav-links { text-align: center; margin-bottom: 30px; }
        .nav-link { 
            color: white; 
            text-decoration: none; 
            margin: 0 15px; 
            padding: 10px 20px; 
            border: 2px solid white; 
            border-radius: 25px; 
            transition: all 0.3s;
            display: inline-block;
        }
        .nav-link:hover { background: white; color: #667eea; transform: translateY(-2px); }
        .nav-link.active { background: white; color: #667eea; }
        
        .add-stock-section {
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
        }
        .add-stock-input {
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            margin: 0 10px;
            width: 200px;
        }
        .add-stock-btn {
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin: 0 5px;
        }
        .add-stock-btn:hover { transform: translateY(-2px); }
        
        .watchlist-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }
        .stat-value { font-size: 24px; font-weight: bold; color: #2c3e50; }
        .stat-label { color: #666; margin-top: 5px; }
        
        .watchlist-table {
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            overflow: hidden;
        }
        .table-header {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 15px;
            display: grid;
            grid-template-columns: 80px 1fr 150px 120px 100px 120px 100px;
            gap: 15px;
            font-weight: bold;
        }
        .table-row {
            padding: 15px;
            display: grid;
            grid-template-columns: 80px 1fr 150px 120px 100px 120px 100px;
            gap: 15px;
            align-items: center;
            border-bottom: 1px solid #eee;
        }
        .table-row:hover { background: #f8f9fa; }
        .table-row:last-child { border-bottom: none; }
        
        .symbol { font-weight: bold; color: #2c3e50; }
        .company-name { color: #666; font-size: 14px; }
        .status-active { color: #28a745; font-weight: bold; }
        .status-inactive { color: #dc3545; font-weight: bold; }
        .btn { 
            padding: 5px 10px; 
            border: none; 
            border-radius: 12px; 
            cursor: pointer; 
            font-size: 12px; 
            margin: 0 2px;
        }
        .btn-toggle { background: #ffc107; color: white; }
        .btn-remove { background: #dc3545; color: white; }
        .btn:hover { transform: translateY(-1px); }
        
        .loading { text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 Stock Watchlist</h1>
            <p>Manage which stocks to analyze</p>
        </div>
        
        <div class="nav-links">
            <a href="/" class="nav-link">🏠 Home</a>
            <a href="/portfolio" class="nav-link">📊 Portfolio</a>
            <a href="/watchlist" class="nav-link active">📋 Watchlist</a>
            <a href="/advanced" class="nav-link">🚀 Advanced</a>
        </div>
        
        <div class="add-stock-section">
            <h3>Add New Stock</h3>
            <input type="text" id="newStockSymbol" class="add-stock-input" placeholder="Enter stock symbol (e.g., AAPL)" maxlength="10">
            <button class="add-stock-btn" onclick="addStock()">➕ Add Stock</button>
            <button class="add-stock-btn" onclick="loadWatchlist()" style="background: #3498db;">🔄 Refresh</button>
        </div>
        
        <div class="watchlist-stats" id="watchlistStats">
            <div class="stat-card">
                <div class="stat-value" id="totalStocks">0</div>
                <div class="stat-label">Total Stocks</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="activeStocks">0</div>
                <div class="stat-label">Active for Analysis</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="userAdded">0</div>
                <div class="stat-label">Added by You</div>
            </div>
        </div>
        
        <div class="watchlist-table">
            <div class="table-header">
                <div>Symbol</div>
                <div>Company</div>
                <div>Sector</div>
                <div>Market Cap</div>
                <div>Status</div>
                <div>Source</div>
                <div>Actions</div>
            </div>
            <div id="watchlistData">
                <div class="loading">Loading watchlist...</div>
            </div>
        </div>
    </div>
    
    <script>
        function loadWatchlist() {
            fetch('/api/watchlist')
                .then(response => response.json())
                .then(data => {
                    displayWatchlist(data);
                    updateStats(data);
                })
                .catch(error => {
                    console.error('Error loading watchlist:', error);
                    document.getElementById('watchlistData').innerHTML = 
                        '<div class="loading">Error loading watchlist</div>';
                });
        }
        
        function displayWatchlist(stocks) {
            const container = document.getElementById('watchlistData');
            container.innerHTML = '';
            
            if (stocks.length === 0) {
                container.innerHTML = '<div class="loading">No stocks in watchlist</div>';
                return;
            }
            
            stocks.forEach(stock => {
                const row = document.createElement('div');
                row.className = 'table-row';
                
                const statusClass = stock.is_active ? 'status-active' : 'status-inactive';
                const statusText = stock.is_active ? 'Active' : 'Inactive';
                const toggleText = stock.is_active ? 'Disable' : 'Enable';
                const sourceText = stock.added_by_user ? 'You' : 'Default';
                
                row.innerHTML = `
                    <div class="symbol">${stock.symbol}</div>
                    <div>
                        <div style="font-weight: bold;">${stock.company_name}</div>
                    </div>
                    <div>${stock.sector}</div>
                    <div>${stock.market_cap}</div>
                    <div class="${statusClass}">${statusText}</div>
                    <div>${sourceText}</div>
                    <div>
                        <button class="btn btn-toggle" onclick="toggleStock('${stock.symbol}', ${!stock.is_active})">${toggleText}</button>
                        ${stock.added_by_user ? `<button class="btn btn-remove" onclick="removeStock('${stock.symbol}')">Remove</button>` : ''}
                    </div>
                `;
                
                container.appendChild(row);
            });
        }
        
        function updateStats(stocks) {
            const total = stocks.length;
            const active = stocks.filter(s => s.is_active).length;
            const userAdded = stocks.filter(s => s.added_by_user).length;
            
            document.getElementById('totalStocks').textContent = total;
            document.getElementById('activeStocks').textContent = active;
            document.getElementById('userAdded').textContent = userAdded;
        }
        
        function addStock() {
            const symbol = document.getElementById('newStockSymbol').value.trim().toUpperCase();
            if (!symbol) {
                alert('Please enter a stock symbol');
                return;
            }
            
            const btn = event.target;
            btn.textContent = '⏳ Adding...';
            btn.disabled = true;
            
            fetch('/api/watchlist/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: symbol})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('newStockSymbol').value = '';
                    loadWatchlist();
                    alert(`✅ ${data.message}`);
                } else {
                    alert(`❌ ${data.message}`);
                }
            })
            .catch(error => {
                alert('Error adding stock: ' + error.message);
            })
            .finally(() => {
                btn.textContent = '➕ Add Stock';
                btn.disabled = false;
            });
        }
        
        function toggleStock(symbol, newStatus) {
            fetch('/api/watchlist/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: symbol, is_active: newStatus})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadWatchlist();
                } else {
                    alert('Error: ' + data.message);
                }
            });
        }
        
        function removeStock(symbol) {
            if (confirm(`Remove ${symbol} from watchlist?`)) {
                fetch('/api/watchlist/remove', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({symbol: symbol})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadWatchlist();
                    } else {
                        alert('Error: ' + data.message);
                    }
                });
            }
        }
        
        // Allow Enter key to add stock
        document.getElementById('newStockSymbol').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                addStock();
            }
        });
        
        // Load watchlist on page load
        document.addEventListener('DOMContentLoaded', loadWatchlist);
    </script>
</body>
</html>
    ''')

# ===== WATCHLIST API ROUTES =====

@app.route('/api/watchlist')
def get_watchlist():
    """Get watchlist details"""
    try:
        watchlist = stock_list_manager.get_watchlist_details()
        return jsonify(watchlist)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """Add stock to watchlist"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').strip().upper()
        
        if not symbol:
            return jsonify({"success": False, "message": "Symbol required"})
        
        result = stock_list_manager.add_stock_to_watchlist(symbol)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """Remove stock from watchlist"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').strip().upper()
        
        if not symbol:
            return jsonify({"success": False, "message": "Symbol required"})
        
        result = stock_list_manager.remove_stock_from_watchlist(symbol)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/watchlist/toggle', methods=['POST'])
def toggle_watchlist_stock():
    """Enable/disable stock in analysis"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').strip().upper()
        is_active = data.get('is_active', True)
        
        if not symbol:
            return jsonify({"success": False, "message": "Symbol required"})
        
        result = stock_list_manager.toggle_stock_active(symbol, is_active)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})




@app.route('/portfolio')
def portfolio_dashboard():
    """Portfolio dashboard page"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>📊 My Portfolio - Stock Analysis</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .nav-links { text-align: center; margin-bottom: 30px; }
        .nav-link { 
            color: white; 
            text-decoration: none; 
            margin: 0 15px; 
            padding: 10px 20px; 
            border: 2px solid white; 
            border-radius: 25px; 
            transition: all 0.3s;
        }
        .nav-link:hover { background: white; color: #667eea; }
        .nav-link.active { background: white; color: #667eea; }
        
        .portfolio-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .summary-value { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
        .summary-label { color: #666; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
        
        .portfolio-actions {
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
        }
        .action-btn {
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin: 0 10px;
            transition: all 0.3s;
        }
        .action-btn:hover { transform: translateY(-2px); }
        .action-btn.danger { background: linear-gradient(45deg, #dc3545, #c82333); }
        
        .portfolio-stocks {
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .stocks-header {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 15px;
            display: grid;
            grid-template-columns: 100px 1fr 100px 100px 100px 100px 100px;
            gap: 15px;
            font-weight: bold;
        }
        .stock-row {
            padding: 15px;
            display: grid;
            grid-template-columns: 100px 1fr 100px 100px 100px 100px 100px;
            gap: 15px;
            align-items: center;
            border-bottom: 1px solid #eee;
        }
        .stock-row:last-child { border-bottom: none; }
        .stock-row:hover { background: #f8f9fa; }
        
        .symbol { font-weight: bold; color: #2c3e50; }
        .signal { 
            padding: 4px 8px; 
            border-radius: 12px; 
            font-size: 12px; 
            color: white; 
            text-align: center; 
        }
        .strong-buy { background: #27ae60; }
        .buy { background: #28a745; }
        .hold { background: #ffc107; }
        .sell { background: #dc3545; }
        .strong-sell { background: #c82333; }
        
        .remove-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 12px;
        }
        .remove-btn:hover { background: #c82333; }
        
        .empty-portfolio {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .loading { text-align: center; padding: 20px; }
        .spinner { 
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 My Portfolio</h1>
            <p>Track your favorite stocks and AI prediction performance</p>
        </div>
        
        <div class="nav-links">
            <a href="/" class="nav-link">🏠 Home</a>
            <a href="/portfolio" class="nav-link">📊 Portfolio</a>
            <a href="/watchlist" class="nav-link active">📋 Watchlist</a>
            <a href="/advanced" class="nav-link">🚀 Advanced</a>
        </div>
        
        <div class="portfolio-summary" id="portfolioSummary">
            <div class="summary-card">
                <div class="summary-value" id="totalStocks">0</div>
                <div class="summary-label">Stocks Tracked</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalInvested">$0</div>
                <div class="summary-label">Total "Invested"</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalCurrent">$0</div>
                <div class="summary-label">Current Value</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalGain">$0</div>
                <div class="summary-label">Total Gain/Loss</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalGainPercent">0%</div>
                <div class="summary-label">Total Return</div>
            </div>
        </div>
        
        <div class="portfolio-actions">
            <button class="action-btn" onclick="updatePrices()">📈 Update Prices</button>
            <button class="action-btn danger" onclick="clearPortfolio()">🗑️ Clear Portfolio</button>
        </div>
        
        <div class="portfolio-stocks">
            <div class="stocks-header">
                <div>Symbol</div>
                <div>Added Date</div>
                <div>Added Price</div>
                <div>Current Price</div>
                <div>Gain/Loss</div>
                <div>Signal When Added</div>
                <div>Action</div>
            </div>
            <div id="portfolioStocks">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Loading portfolio...</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function loadPortfolio() {
            fetch('/api/portfolio')
                .then(response => response.json())
                .then(data => {
                    updateSummary(data);
                    displayPortfolioStocks(data.stocks);
                })
                .catch(error => {
                    console.error('Error loading portfolio:', error);
                    document.getElementById('portfolioStocks').innerHTML = 
                        '<div class="empty-portfolio">Error loading portfolio</div>';
                });
        }
        
        function updateSummary(data) {
            document.getElementById('totalStocks').textContent = data.stocks.length;
            document.getElementById('totalInvested').textContent = '$' + data.total_invested.toFixed(2);
            document.getElementById('totalCurrent').textContent = '$' + data.total_current.toFixed(2);
            
            const gainElement = document.getElementById('totalGain');
            const gainPercentElement = document.getElementById('totalGainPercent');
            
            gainElement.textContent = (data.total_gain >= 0 ? '+' : '') + '$' + data.total_gain.toFixed(2);
            gainPercentElement.textContent = (data.total_gain_percent >= 0 ? '+' : '') + data.total_gain_percent.toFixed(1) + '%';
            
            gainElement.className = 'summary-value ' + (data.total_gain >= 0 ? 'positive' : 'negative');
            gainPercentElement.className = 'summary-value ' + (data.total_gain_percent >= 0 ? 'positive' : 'negative');
        }
        
        function displayPortfolioStocks(stocks) {
            const container = document.getElementById('portfolioStocks');
            
            if (stocks.length === 0) {
                container.innerHTML = '<div class="empty-portfolio">No stocks in portfolio yet.<br>Go to the <a href="/">main page</a> to add stocks!</div>';
                return;
            }
            
            container.innerHTML = '';
            
            stocks.forEach(stock => {
                const gain = stock.current_price - stock.added_price;
                const gainPercent = (gain / stock.added_price) * 100;
                const gainClass = gain >= 0 ? 'positive' : 'negative';
                const signalClass = stock.signal_when_added.toLowerCase().replace(' ', '-');
                
                const row = document.createElement('div');
                row.className = 'stock-row';
                row.innerHTML = `
                    <div class="symbol">${stock.symbol}</div>
                    <div>${stock.added_date}</div>
                    <div>$${stock.added_price.toFixed(2)}</div>
                    <div>$${stock.current_price.toFixed(2)}</div>
                    <div class="${gainClass}">${gain >= 0 ? '+' : ''}$${gain.toFixed(2)} (${gainPercent.toFixed(1)}%)</div>
                    <div class="signal ${signalClass}">${stock.signal_when_added}</div>
                    <div><button class="remove-btn" onclick="removeFromPortfolio('${stock.symbol}')">Remove</button></div>
                `;
                container.appendChild(row);
            });
        }
        
        function removeFromPortfolio(symbol) {
            if (confirm(`Remove ${symbol} from portfolio?`)) {
                fetch('/api/portfolio/remove', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({symbol: symbol})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadPortfolio();
                    } else {
                        alert('Error: ' + data.message);
                    }
                });
            }
        }
        
        function updatePrices() {
            document.getElementById('portfolioStocks').innerHTML = '<div class="loading"><div class="spinner"></div><p>Updating prices...</p></div>';
            
            fetch('/api/portfolio/update')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadPortfolio();
                    } else {
                        alert('Error updating prices: ' + data.message);
                    }
                });
        }
        
        function clearPortfolio() {
            if (confirm('Are you sure you want to clear your entire portfolio?')) {
                fetch('/api/portfolio/clear', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            loadPortfolio();
                        } else {
                            alert('Error: ' + data.message);
                        }
                    });
            }
        }
        
        // Load portfolio on page load
        document.addEventListener('DOMContentLoaded', loadPortfolio);
    </script>
</body>
</html>
    ''')

# ===== NEW: PORTFOLIO API ROUTES =====

@app.route('/api/portfolio')
def get_portfolio():
    """Get portfolio performance data"""
    try:
        # Update prices first
        portfolio_manager.update_portfolio_prices(analyzer)
        
        # Get performance data
        performance = portfolio_manager.get_portfolio_performance()
        return jsonify(performance)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/portfolio/add', methods=['POST'])
def add_to_portfolio():
    """Add stock to portfolio"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({"success": False, "message": "Symbol required"})
        
        # Get current analysis
        analysis = analyzer.analyze_stock(symbol)
        if not analysis:
            return jsonify({"success": False, "message": "Could not analyze stock"})
        
        # Add to portfolio
        result = portfolio_manager.add_to_portfolio(
            symbol,
            analysis['current_price'],
            analysis['signal'],
            analysis['confidence']
        )
        
        # Save prediction for tracking
        portfolio_manager.save_prediction(symbol, analysis)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/portfolio/remove', methods=['POST'])
def remove_from_portfolio():
    """Remove stock from portfolio"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({"success": False, "message": "Symbol required"})
        
        result = portfolio_manager.remove_from_portfolio(symbol)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/portfolio/update')
def update_portfolio_prices():
    """Update portfolio prices"""
    try:
        success = portfolio_manager.update_portfolio_prices(analyzer)
        if success:
            return jsonify({"success": True, "message": "Prices updated successfully"})
        else:
            return jsonify({"success": False, "message": "Error updating prices"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/portfolio/clear', methods=['POST'])
def clear_portfolio():
    """Clear entire portfolio"""
    try:
        conn = sqlite3.connect('portfolio.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_portfolios WHERE user_id = ?', ('default_user',))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Portfolio cleared"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ===== MODIFY EXISTING STOCK DISPLAY TO ADD "ADD TO PORTFOLIO" BUTTONS =====


# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

class AdvancedStockAnalyzer:
    def __init__(self):
        # Get market benchmark data (S&P 500)
        self.market_data = None
        self.risk_free_rate = 0.045  # Current 3-month Treasury rate (~4.5%)
        
    def get_stock_list(self):
        """Get current active stock list"""
        return stock_list_manager.get_active_stocks()
    
    def get_market_data(self):
        """Get S&P 500 data for relative performance analysis"""
        try:
            spy = yf.Ticker("SPY")
            market_df = spy.history(period="3mo")
            if not market_df.empty:
                market_df.columns = [col.lower() for col in market_df.columns]
                self.market_data = market_df
                print("✅ Market benchmark data loaded")
            else:
                print("⚠️ Could not load market data")
        except Exception as e:
            print(f"⚠️ Market data error: {e}")
    
    def get_stock_data(self, symbol):
        """Get comprehensive stock data"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1y")  # 1 year for better analysis
            
            if df.empty:
                return None
                
            df.columns = [col.lower() for col in df.columns]
            
            # Calculate returns
            df['returns'] = df['close'].pct_change()
            df['cumulative_returns'] = (1 + df['returns']).cumprod()
            
            return df
            
        except Exception as e:
            print(f"❌ Error getting {symbol}: {e}")
            return None
    
    def calculate_technical_indicators(self, df):
        """Calculate comprehensive technical indicators"""
        try:
            # Moving averages
            df['ma_20'] = df['close'].rolling(window=20).mean()
            df['ma_50'] = df['close'].rolling(window=50).mean()
            df['ma_200'] = df['close'].rolling(window=200).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = df['close'].ewm(span=12).mean()
            exp2 = df['close'].ewm(span=26).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            
            # Bollinger Bands
            df['bb_ma'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_ma'] + (df['bb_std'] * 2)
            df['bb_lower'] = df['bb_ma'] - (df['bb_std'] * 2)
            
            # Volatility
            df['volatility'] = df['returns'].rolling(window=20).std() * np.sqrt(252)  # Annualized
            
            return df
            
        except Exception as e:
            print(f"Error calculating indicators: {e}")
            return None
    
    def calculate_probability_ranges(self, df):
        """Calculate probability ranges for different time horizons with NaN handling"""
        try:
            current_price = df['close'].iloc[-1]
            if pd.isna(current_price):
                return None
                
            returns = df['returns'].dropna()
            
            # Need minimum data for reliable calculations
            if len(returns) < 30:
                print("⚠️ Limited data for probability calculations")
                # Return conservative estimates
                return {
                    '1_week': {
                        'expected_price': current_price,
                        'prob_68_range': [current_price * 0.98, current_price * 1.02],
                        'prob_95_range': [current_price * 0.95, current_price * 1.05],
                        'expected_return': 0.0,
                        'volatility': 5.0
                    },
                    '1_month': {
                        'expected_price': current_price,
                        'prob_68_range': [current_price * 0.95, current_price * 1.05],
                        'prob_95_range': [current_price * 0.90, current_price * 1.10],
                        'expected_return': 0.0,
                        'volatility': 10.0
                    },
                    '3_months': {
                        'expected_price': current_price,
                        'prob_68_range': [current_price * 0.90, current_price * 1.10],
                        'prob_95_range': [current_price * 0.80, current_price * 1.20],
                        'expected_return': 0.0,
                        'volatility': 15.0
                    }
                }
            
            # Calculate statistics
            mean_return = returns.mean()
            std_return = returns.std()
            
            # Handle NaN in statistics
            if pd.isna(mean_return) or pd.isna(std_return):
                mean_return = 0.0
                std_return = 0.02  # 2% default daily volatility
            
            # Time horizons (in trading days)
            horizons = {
                '1_week': 5,
                '1_month': 22,
                '3_months': 66
            }
            
            probability_ranges = {}
            
            for period, days in horizons.items():
                # Adjust for time horizon
                horizon_mean = mean_return * days
                horizon_std = std_return * np.sqrt(days)
                
                # Calculate probability ranges (normal distribution assumption)
                expected_price = current_price * (1 + horizon_mean)
                
                # 68% confidence interval (1 standard deviation)
                prob_68_low = current_price * (1 + horizon_mean - horizon_std)
                prob_68_high = current_price * (1 + horizon_mean + horizon_std)
                
                # 95% confidence interval (2 standard deviations)
                prob_95_low = current_price * (1 + horizon_mean - 2*horizon_std)
                prob_95_high = current_price * (1 + horizon_mean + 2*horizon_std)
                
                # Ensure positive prices
                prob_68_low = max(prob_68_low, current_price * 0.5)
                prob_95_low = max(prob_95_low, current_price * 0.3)
                
                probability_ranges[period] = {
                    'expected_price': expected_price,
                    'prob_68_range': [prob_68_low, prob_68_high],
                    'prob_95_range': [prob_95_low, prob_95_high],
                    'expected_return': horizon_mean * 100,
                    'volatility': horizon_std * 100
                }
            
            return probability_ranges
            
        except Exception as e:
            print(f"Error calculating probability ranges: {e}")
            return None

    
    def calculate_risk_metrics(self, df):
        """Calculate risk-adjusted return metrics with NaN handling"""
        try:
            returns = df['returns'].dropna()
            
            if len(returns) < 30:
                print("⚠️ Limited data for risk metrics")
                return {
                    'annual_return': 0.0,
                    'annual_volatility': 15.0,
                    'sharpe_ratio': 0.0,
                    'sortino_ratio': 0.0,
                    'max_drawdown': -5.0,
                    'calmar_ratio': 0.0
                }
            
            # Annualized metrics
            annual_return = returns.mean() * 252
            annual_volatility = returns.std() * np.sqrt(252)
            
            # Handle NaN in calculations
            if pd.isna(annual_return) or pd.isna(annual_volatility):
                return {
                    'annual_return': 0.0,
                    'annual_volatility': 15.0,
                    'sharpe_ratio': 0.0,
                    'sortino_ratio': 0.0,
                    'max_drawdown': -5.0,
                    'calmar_ratio': 0.0
                }
            
            # Sharpe Ratio
            excess_return = annual_return - self.risk_free_rate
            sharpe_ratio = excess_return / annual_volatility if annual_volatility > 0 else 0
            
            # Sortino Ratio (downside deviation)
            negative_returns = returns[returns < 0]
            downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else annual_volatility
            sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
            
            # Maximum Drawdown
            cumulative_returns = (1 + returns).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - rolling_max) / rolling_max
            max_drawdown = drawdown.min()
            
            # Handle NaN in drawdown
            if pd.isna(max_drawdown):
                max_drawdown = -0.05  # Default -5%
            
            # Calmar Ratio
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            return {
                'annual_return': annual_return * 100,
                'annual_volatility': annual_volatility * 100,
                'sharpe_ratio': sharpe_ratio,
                'sortino_ratio': sortino_ratio,
                'max_drawdown': max_drawdown * 100,
                'calmar_ratio': calmar_ratio
            }
            
        except Exception as e:
            print(f"Error calculating risk metrics: {e}")
            return {
                'annual_return': 0.0,
                'annual_volatility': 15.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'max_drawdown': -5.0,
                'calmar_ratio': 0.0
            }
        
    
    def calculate_relative_performance(self, df):
        """Calculate performance relative to market benchmark"""
        try:
            if self.market_data is None:
                return None
                
            # Align dates
            stock_returns = df['returns'].dropna()
            market_returns = self.market_data['close'].pct_change().dropna()
            
            # Find common dates
            common_dates = stock_returns.index.intersection(market_returns.index)
            if len(common_dates) < 20:
                return None
                
            stock_aligned = stock_returns.loc[common_dates]
            market_aligned = market_returns.loc[common_dates]
            
            # Calculate metrics
            stock_annual = stock_aligned.mean() * 252
            market_annual = market_aligned.mean() * 252
            
            # Beta calculation
            covariance = np.cov(stock_aligned, market_aligned)[0, 1]
            market_variance = np.var(market_aligned)
            beta = covariance / market_variance if market_variance > 0 else 1
            
            # Alpha calculation
            alpha = stock_annual - (self.risk_free_rate + beta * (market_annual - self.risk_free_rate))
            
            # Correlation
            correlation = np.corrcoef(stock_aligned, market_aligned)[0, 1]
            
            # Relative performance
            relative_performance = (stock_annual - market_annual) * 100
            
            return {
                'beta': beta,
                'alpha': alpha * 100,
                'correlation': correlation,
                'relative_performance': relative_performance,
                'market_return': market_annual * 100
            }
            
        except Exception as e:
            print(f"Error calculating relative performance: {e}")
            return None
    
    def generate_signal(self, df):
        """Generate trading signal based on multiple factors with NaN handling"""
        try:
            latest = df.iloc[-1]
            
            # Check for basic data availability
            if pd.isna(latest['close']) or pd.isna(latest['rsi']):
                return {
                    'signal': 'HOLD',
                    'confidence': 25,
                    'strength': 0,
                    'reasons': ['Insufficient data for analysis']
                }
            
            # Technical signals
            signals = []
            strength = 0
            
            # RSI signal
            rsi = latest['rsi']
            if not pd.isna(rsi):
                if rsi < 30:
                    signals.append("Oversold (RSI < 30)")
                    strength += 3
                elif rsi > 70:
                    signals.append("Overbought (RSI > 70)")
                    strength -= 3
                else:
                    signals.append(f"RSI {rsi:.1f} - Neutral zone")
            
            # Moving average signals (handle NaN)
            close_price = latest['close']
            ma_20 = latest['ma_20'] if not pd.isna(latest['ma_20']) else close_price
            ma_50 = latest['ma_50'] if not pd.isna(latest['ma_50']) else close_price
            
            if close_price > ma_20 > ma_50:
                signals.append("Strong uptrend")
                strength += 2
            elif close_price < ma_20 < ma_50:
                signals.append("Strong downtrend")
                strength -= 2
            elif close_price > ma_20:
                signals.append("Above 20-day average")
                strength += 1
            else:
                signals.append("Below 20-day average")
                strength -= 1
            
            # MACD signal (handle NaN)
            if not pd.isna(latest['macd']) and not pd.isna(latest['macd_signal']):
                if latest['macd'] > latest['macd_signal']:
                    signals.append("Positive momentum")
                    strength += 1
                else:
                    signals.append("Negative momentum")
                    strength -= 1
            
            # Bollinger Bands (handle NaN)
            if not pd.isna(latest['bb_lower']) and not pd.isna(latest['bb_upper']):
                if close_price < latest['bb_lower']:
                    signals.append("Below lower Bollinger Band")
                    strength += 1
                elif close_price > latest['bb_upper']:
                    signals.append("Above upper Bollinger Band")
                    strength -= 1
            
            # Determine overall signal
            if strength >= 3:
                signal = "STRONG BUY"
                confidence = min(95, 60 + strength * 5)
            elif strength >= 1:
                signal = "BUY"
                confidence = min(85, 50 + strength * 8)
            elif strength <= -3:
                signal = "STRONG SELL"
                confidence = min(95, 60 + abs(strength) * 5)
            elif strength <= -1:
                signal = "SELL"
                confidence = min(85, 50 + abs(strength) * 8)
            else:
                signal = "HOLD"
                confidence = 50
            
            return {
                'signal': signal,
                'confidence': confidence,
                'strength': strength,
                'reasons': signals
            }
            
        except Exception as e:
            print(f"Error generating signal: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 25,
                'strength': 0,
                'reasons': ['Error in signal calculation']
            }

    
    def analyze_stock(self, symbol):
        """Complete analysis of a single stock with NaN handling"""
        print(f"📊 Analyzing {symbol}...")
        
        # Get data
        df = self.get_stock_data(symbol)
        if df is None:
            return None
            
        df = self.calculate_technical_indicators(df)
        if df is None:
            return None
        
        # Get latest values
        latest = df.iloc[-1]
        
        # Helper function to safely convert values and handle NaN
        def safe_float(value, default=0.0):
            """Convert value to float, handling NaN and None"""
            try:
                if pd.isna(value) or value is None:
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_round(value, decimals=2, default=0.0):
            """Safely round a value, handling NaN"""
            safe_val = safe_float(value, default)
            return round(safe_val, decimals)
        
        # Validate that we have minimum required data
        if pd.isna(latest['close']) or pd.isna(latest['rsi']):
            print(f"❌ Insufficient data for {symbol}")
            return None
        
        # Calculate all metrics with NaN handling
        try:
            probability_ranges = self.calculate_probability_ranges(df)
            risk_metrics = self.calculate_risk_metrics(df)
            relative_performance = self.calculate_relative_performance(df)
            signal_data = self.generate_signal(df)
        except Exception as e:
            print(f"❌ Error in calculations for {symbol}: {e}")
            return None
        
        # Safely extract values with NaN handling
        current_price = safe_float(latest['close'])
        rsi_value = safe_float(latest['rsi'])
        volume_value = safe_float(latest['volume'])
        volatility_value = safe_float(latest['volatility']) if 'volatility' in latest else 0.0
        
        # Handle moving averages that might be NaN for new stocks
        ma_20 = safe_float(latest['ma_20'], current_price)  # Default to current price if NaN
        ma_50 = safe_float(latest['ma_50'], current_price)
        ma_200 = safe_float(latest['ma_200'], current_price)
        macd_value = safe_float(latest['macd'])
        
        # Calculate Bollinger Band position safely
        bb_upper = safe_float(latest['bb_upper'], current_price * 1.02)
        bb_lower = safe_float(latest['bb_lower'], current_price * 0.98)
        bb_position = 50.0  # Default to middle
        if bb_upper != bb_lower:
            bb_position = ((current_price - bb_lower) / (bb_upper - bb_lower)) * 100
            bb_position = max(0, min(100, bb_position))  # Clamp between 0-100
        
        # Compile results with safe values
        result = {
            'symbol': symbol,
            'current_price': safe_round(current_price, 2),
            'signal': signal_data['signal'] if signal_data else 'HOLD',
            'confidence': safe_round(signal_data['confidence'] if signal_data else 50, 1),
            'rsi': safe_round(rsi_value, 1),
            'volume': int(safe_float(volume_value)),
            'volatility': safe_round(volatility_value, 1),
            
            # Probability ranges (already handled in the function)
            'probability_ranges': probability_ranges,
            
            # Risk metrics (already handled in the function)
            'risk_metrics': risk_metrics,
            
            # Relative performance (already handled in the function)
            'relative_performance': relative_performance,
            
            # Technical details with safe values
            'technical_details': {
                'ma_20': safe_round(ma_20, 2),
                'ma_50': safe_round(ma_50, 2),
                'ma_200': safe_round(ma_200, 2),
                'macd': safe_round(macd_value, 3),
                'bb_position': safe_round(bb_position, 1),
                'reasons': signal_data['reasons'] if signal_data else ['Insufficient data for analysis']
            }
        }
        
        return result
    
    
    def analyze_all_stocks(self):
        """Analyze all stocks in the dynamic watchlist"""
        print("🚀 Starting Advanced Stock Analysis...")
        
        # Get current stock list dynamically
        current_stock_list = self.get_stock_list()
        print(f"📊 Analyzing {len(current_stock_list)} stocks from watchlist")
        
        # Load market data first
        self.get_market_data()
        
        results = []
        failed_stocks = []
        
        for i, symbol in enumerate(current_stock_list, 1):
            print(f"\n📊 Progress: {i}/{len(current_stock_list)} - {symbol}")
            
            result = self.analyze_stock(symbol)
            if result:
                results.append(result)
                print(f"✅ {symbol}: {result['signal']} ({result['confidence']:.0f}%)")
            else:
                failed_stocks.append(symbol)
                print(f"❌ Failed: {symbol}")
            
            time.sleep(0.3)  # Small delay
        
        print(f"\n🎉 Analysis complete! {len(results)} stocks analyzed")
        if failed_stocks:
            print(f"❌ Failed: {', '.join(failed_stocks)}")
        
        return results

# Telegram Bot Integration
class TelegramBot:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.bot_token = TELEGRAM_BOT_TOKEN
        
    def send_message(self, chat_id, text, parse_mode="HTML"):
        """Send message to Telegram"""
        if not self.bot_token:
            return None
            
        try:
            url = f"{TELEGRAM_API_URL}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            response = requests.post(url, json=payload)
            return response.json()
        except Exception as e:
            print(f"Error sending message: {e}")
            return None
    
    def format_stock_analysis(self, stock):
        """Format stock analysis for Telegram"""
        signal_emoji = {
            'STRONG BUY': '🚀',
            'BUY': '📈',
            'HOLD': '⏸️',
            'SELL': '📉',
            'STRONG SELL': '💥'
        }
        
        emoji = signal_emoji.get(stock['signal'], '❓')
        
        # Basic info
        text = f"""
<b>{emoji} {stock['symbol']} Analysis</b>

💰 <b>Current Price:</b> ${stock['current_price']}
📊 <b>Signal:</b> {stock['signal']} ({stock['confidence']}% confidence)
📈 <b>RSI:</b> {stock['rsi']}

<b>📅 Price Predictions:</b>
"""
        
        # Add probability ranges
        if stock.get('probability_ranges'):
            for period, data in stock['probability_ranges'].items():
                period_name = period.replace('_', ' ').title()
                expected = data['expected_price']
                range_68 = data['prob_68_range']
                
                text += f"<b>{period_name}:</b> ${expected:.2f}\n"
                text += f"  68% range: ${range_68[0]:.2f} - ${range_68[1]:.2f}\n"
        
        # Add risk metrics
        if stock.get('risk_metrics'):
            risk = stock['risk_metrics']
            text += f"""
<b>⚖️ Risk Metrics:</b>
Sharpe Ratio: {risk['sharpe_ratio']:.2f}
Annual Return: {risk['annual_return']:.1f}%
Max Drawdown: {risk['max_drawdown']:.1f}%
"""
        
        # Add relative performance
        if stock.get('relative_performance'):
            rel = stock['relative_performance']
            text += f"""
<b>📊 vs S&P 500:</b>
Performance: {rel['relative_performance']:+.1f}%
Beta: {rel['beta']:.2f}
Alpha: {rel['alpha']:+.2f}%
"""
        
        return text
    
    def process_command(self, message):
        """Process Telegram commands"""
        chat_id = message['chat']['id']
        text = message.get('text', '').lower()
        
        if text == '/start':
            welcome_text = """
🚀 <b>Welcome to Advanced Stock Analysis Bot!</b>

Available commands:
/analyze - Get analysis of all stocks
/stock SYMBOL - Get specific stock analysis (e.g., /stock AAPL)
/top - Get top 5 buy signals
/help - Show this help message

Example: <code>/stock TSLA</code>
"""
            self.send_message(chat_id, welcome_text)
            
        elif text == '/analyze':
            self.send_message(chat_id, "🤖 Starting analysis... This may take a minute.")
            
            # Run analysis in background
            def analyze_and_send():
                try:
                    results = self.analyzer.analyze_all_stocks()
                    if results:
                        # Send summary
                        summary = self.create_summary(results)
                        self.send_message(chat_id, summary)
                        
                        # Send top signals
                        top_signals = [r for r in results if r['signal'] in ['STRONG BUY', 'BUY']][:5]
                        for stock in top_signals:
                            analysis = self.format_stock_analysis(stock)
                            self.send_message(chat_id, analysis)
                    else:
                        self.send_message(chat_id, "❌ Analysis failed. Please try again.")
                except Exception as e:
                    self.send_message(chat_id, f"❌ Error: {str(e)}")
            
            threading.Thread(target=analyze_and_send).start()
            
        elif text.startswith('/stock '):
            symbol = text.replace('/stock ', '').upper()
            self.send_message(chat_id, f"🔍 Analyzing {symbol}...")
            
            # Analyze single stock
            def analyze_single_and_send():
                try:
                    result = self.analyzer.analyze_stock(symbol)
                    if result:
                        analysis = self.format_stock_analysis(result)
                        self.send_message(chat_id, analysis)
                    else:
                        self.send_message(chat_id, f"❌ Could not analyze {symbol}. Please check the symbol.")
                except Exception as e:
                    self.send_message(chat_id, f"❌ Error: {str(e)}")
            
            threading.Thread(target=analyze_single_and_send).start()
            
        elif text == '/top':
            self.send_message(chat_id, "🔍 Finding top signals...")
            
            def get_top_signals():
                try:
                    results = self.analyzer.analyze_all_stocks()
                    if results:
                        # Sort by confidence and signal strength
                        buy_signals = [r for r in results if r['signal'] in ['STRONG BUY', 'BUY']]
                        buy_signals.sort(key=lambda x: x['confidence'], reverse=True)
                        
                        if buy_signals:
                            text = "🚀 <b>Top Buy Signals:</b>\n\n"
                            for i, stock in enumerate(buy_signals[:5], 1):
                                text += f"{i}. <b>{stock['symbol']}</b> - {stock['signal']} ({stock['confidence']}%)\n"
                                text += f"   Price: ${stock['current_price']}\n\n"
                            
                            self.send_message(chat_id, text)
                        else:
                            self.send_message(chat_id, "📊 No buy signals found right now.")
                    else:
                        self.send_message(chat_id, "❌ Analysis failed.")
                except Exception as e:
                    self.send_message(chat_id, f"❌ Error: {str(e)}")
            
            threading.Thread(target=get_top_signals).start()
            
        elif text == '/help':
            help_text = """
<b>📚 Available Commands:</b>

/analyze - Full analysis of all stocks
/stock SYMBOL - Analyze specific stock
/top - Top 5 buy signals
/help - Show this help

<b>Examples:</b>
<code>/stock AAPL</code>
<code>/stock TSLA</code>
<code>/stock GOOGL</code>

<b>💡 Tips:</b>
• Analysis takes 1-2 minutes
• Use /top for quick overview
• Results include probability ranges and risk metrics
"""
            self.send_message(chat_id, help_text)
            
        else:
            self.send_message(chat_id, "❓ Unknown command. Use /help to see available commands.")
    
    def create_summary(self, results):
        """Create analysis summary"""
        signals = {}
        for result in results:
            signal = result['signal']
            signals[signal] = signals.get(signal, 0) + 1
        
        total = len(results)
        
        summary = f"""
📊 <b>Market Analysis Summary</b>
Total stocks analyzed: {total}

🚀 Strong Buy: {signals.get('STRONG BUY', 0)}
📈 Buy: {signals.get('BUY', 0)}
⏸️ Hold: {signals.get('HOLD', 0)}
📉 Sell: {signals.get('SELL', 0)}
💥 Strong Sell: {signals.get('STRONG SELL', 0)}

🎯 <b>Top signals coming next...</b>
"""
        return summary

# Create instances
analyzer = AdvancedStockAnalyzer()
advanced_analyzer = AdvancedAnalyzer()
telegram_bot = TelegramBot(analyzer) if TELEGRAM_BOT_TOKEN else None

# Web routes
@app.route('/')
def dashboard():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>📊 Advanced Stock Analysis</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.8em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .header p { font-size: 1.2em; opacity: 0.9; }
        
        .analyze-btn {
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            display: block;
            margin: 0 auto 30px;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .analyze-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
        .analyze-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        
        .info-card {
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .loading { text-align: center; color: white; padding: 40px; display: none; }
        .spinner { 
            border: 4px solid rgba(255,255,255,0.3);
            border-top: 4px solid white;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .results { display: none; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.95); padding: 20px; border-radius: 15px; text-align: center; }
        .stat-value { font-size: 28px; font-weight: bold; margin-bottom: 5px; }
        .stat-label { color: #666; }
        
        .stocks-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .stock-card { background: rgba(255,255,255,0.95); padding: 20px; border-radius: 15px; transition: transform 0.3s; }
        .stock-card:hover { transform: translateY(-5px); }
        .stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .symbol { font-size: 20px; font-weight: bold; color: #2c3e50; }
        .signal { padding: 5px 12px; border-radius: 15px; color: white; font-size: 12px; font-weight: bold; }
        .strong-buy { background: linear-gradient(45deg, #27ae60, #2ecc71); }
        .buy { background: linear-gradient(45deg, #28a745, #20c997); }
        .hold { background: linear-gradient(45deg, #ffc107, #fd7e14); }
        .sell { background: linear-gradient(45deg, #dc3545, #fd7e14); }
        .strong-sell { background: linear-gradient(45deg, #dc3545, #c82333); }
        
        .price-info { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .price-item { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px; }
        .price-label { font-size: 12px; color: #666; }
        .price-value { font-weight: bold; color: #2c3e50; }
        
        .metrics { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .metric { text-align: center; padding: 8px; background: #f8f9fa; border-radius: 5px; }
        .metric-label { font-size: 10px; color: #666; }
        .metric-value { font-weight: bold; font-size: 12px; color: #2c3e50; }
        
        .prediction { background: #e8f5e8; padding: 10px; border-radius: 8px; border-left: 4px solid #28a745; }
        .prediction-title { font-weight: bold; margin-bottom: 5px; }
        .prediction-item { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px; }

        .portfolio-btn { background: linear-gradient(45deg, #3498db, #2980b9); color: white; border: none;
            padding: 8px 16px;
            border-radius: 15px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 10px;
        }
        .portfolio-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        .portfolio-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .risk-positive { color: #28a745; }
        .risk-negative { color: #dc3545; }
        .risk-neutral { color: #6c757d; }

        .nav-links { text-align: center; margin-bottom: 30px; }
        .nav-link { 
            color: white; 
            text-decoration: none; 
            margin: 0 15px; 
            padding: 10px 20px; 
            border: 2px solid white; 
            border-radius: 25px; 
            transition: all 0.3s;
            display: inline-block;
        }
        .nav-link:hover { 
            background: white; 
            color: #667eea; 
            transform: translateY(-2px);
        }
        .nav-link.active { 
        background: white; 
        color: #667eea; 
        }
        
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Advanced Stock Analysis</h1>
            <p>Probability ranges • Risk-adjusted returns • Relative performance</p>
        </div>

        <div class="nav-links">
            <a href="/" class="nav-link">🏠 Home</a>
            <a href="/portfolio" class="nav-link">📊 Portfolio</a>
            <a href="/watchlist" class="nav-link active">📋 Watchlist</a>
            <a href="/advanced" class="nav-link">🚀 Advanced</a>
        </div>
        
        <div class="info-card">
            <h3>🚀 Welcome to Your Professional Stock Analysis Tool!</h3>
            <p>This application provides advanced stock analysis with probability ranges, risk-adjusted returns, and relative performance metrics. Click the button below to analyze 20 popular stocks.</p>
            <br>
            <p><strong>Features:</strong></p>
            <ul>
                <li>📈 Probability ranges for 1 week, 1 month, and 3 months</li>
                <li>⚖️ Risk-adjusted returns (Sharpe, Sortino, Calmar ratios)</li>
                <li>📊 Relative performance vs S&P 500 (Beta, Alpha, Correlation)</li>
                <li>🎯 Advanced technical analysis with multiple indicators</li>
            </ul>
        </div>
        
        <button class="analyze-btn" onclick="startAnalysis()" id="analyzeBtn">
            🚀 Analyze Stocks
        </button>
        
        <div class="loading" id="loading">
            <h3>🤖 Running advanced analysis...</h3>
            <div class="spinner"></div>
            <p>Calculating probability ranges and risk metrics...</p>
        </div>
        
        <div class="results" id="results">
            <div class="summary" id="summary"></div>
            <div class="stocks-grid" id="stocksGrid"></div>
        </div>
    </div>
    
    <script>
        function startAnalysis() {
            document.getElementById('analyzeBtn').disabled = true;
            document.getElementById('analyzeBtn').textContent = '⏳ Analyzing...';
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            
            fetch('/api/analyze')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }
                    
                    displayResults(data);
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('results').style.display = 'block';
                })
                .catch(error => {
                    alert('Error: ' + error.message);
                    document.getElementById('loading').style.display = 'none';
                })
                .finally(() => {
                    document.getElementById('analyzeBtn').disabled = false;
                    document.getElementById('analyzeBtn').textContent = '🚀 Analyze Stocks';
                });
        }
        
        function displayResults(stocks) {
            displaySummary(stocks);
            displayStocks(stocks);
        }
        
        function displaySummary(stocks) {
            const signals = stocks.reduce((acc, stock) => {
                acc[stock.signal] = (acc[stock.signal] || 0) + 1;
                return acc;
            }, {});
            
            const summaryDiv = document.getElementById('summary');
            summaryDiv.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value strong-buy">${signals['STRONG BUY'] || 0}</div>
                    <div class="stat-label">Strong Buy</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value buy">${signals['BUY'] || 0}</div>
                    <div class="stat-label">Buy</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value hold">${signals['HOLD'] || 0}</div>
                    <div class="stat-label">Hold</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value sell">${signals['SELL'] || 0}</div>
                    <div class="stat-label">Sell</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value strong-sell">${signals['STRONG SELL'] || 0}</div>
                    <div class="stat-label">Strong Sell</div>
                </div>
            `;
        }
        
        function displayStocks(stocks) {
    const gridDiv = document.getElementById('stocksGrid');
    gridDiv.innerHTML = '';
    
    stocks.forEach(stock => {
        const signalClass = stock.signal.toLowerCase().replace(' ', '-');
        
        const card = document.createElement('div');
        card.className = 'stock-card';
        
        // Create predictions HTML for all timeframes
        let predictionsHTML = '';
        if (stock.probability_ranges) {
            const timeframes = {
                '1_week': '📅 1 Week',
                '1_month': '📅 1 Month', 
                '3_months': '📅 3 Months'
            };
            
            for (const [period, title] of Object.entries(timeframes)) {
                const data = stock.probability_ranges[period];
                if (data) {
                    const expectedChange = ((data.expected_price - stock.current_price) / stock.current_price * 100);
                    const changeClass = expectedChange > 0 ? 'risk-positive' : expectedChange < 0 ? 'risk-negative' : 'risk-neutral';
                    
                    predictionsHTML += `
                        <div class="prediction" style="margin-bottom: 10px;">
                            <div class="prediction-title">${title}</div>
                            <div class="prediction-item">
                                <span>Expected:</span>
                                <span class="${changeClass}">$${data.expected_price.toFixed(2)} (${expectedChange > 0 ? '+' : ''}${expectedChange.toFixed(1)}%)</span>
                            </div>
                            <div class="prediction-item">
                                <span>68% Range:</span>
                                <span>$${data.prob_68_range[0].toFixed(2)} - $${data.prob_68_range[1].toFixed(2)}</span>
                            </div>
                            <div class="prediction-item">
                                <span>95% Range:</span>
                                <span>$${data.prob_95_range[0].toFixed(2)} - $${data.prob_95_range[1].toFixed(2)}</span>
                            </div>
                        </div>
                    `;
                }
            }
        }
        
        card.innerHTML = `
            <div class="stock-header">
                <div class="symbol">${stock.symbol}</div>
                <div class="signal ${signalClass}">${stock.signal}</div>
            </div>
            
            <div class="price-info">
                <div class="price-item">
                    <div class="price-label">Current Price</div>
                    <div class="price-value">$${stock.current_price}</div>
                </div>
                <div class="price-item">
                    <div class="price-label">Confidence</div>
                    <div class="price-value">${stock.confidence}%</div>
                </div>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <div class="metric-label">RSI</div>
                    <div class="metric-value">${stock.rsi}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Volatility</div>
                    <div class="metric-value">${stock.volatility}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Volume</div>
                    <div class="metric-value">${(stock.volume / 1000000).toFixed(1)}M</div>
                </div>
            </div>
            
            ${predictionsHTML}
            
            <div style="margin-top: 15px; text-align: center;">
                <button class="portfolio-btn" onclick="addToPortfolio('${stock.symbol}')">
                    📊 Add to Portfolio
                </button>
            </div>
        `;
        
        gridDiv.appendChild(card);
    });
        }

    function addToPortfolio(symbol) {
    const button = event.target;
    const originalText = button.textContent;
    button.textContent = '⏳ Adding...';
    button.disabled = true;
    
    fetch('/api/portfolio/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symbol: symbol})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            button.textContent = '✅ Added!';
            button.style.background = '#28a745';
            setTimeout(() => {
                button.textContent = originalText;
                button.style.background = '';
                button.disabled = false;
            }, 2000);
        } else {
            alert(data.message);
            button.textContent = originalText;
            button.disabled = false;
        }
    })
    .catch(error => {
        alert('Error adding to portfolio: ' + error.message);
        button.textContent = originalText;
        button.disabled = false;
    });
}

        
    </script>
</body>
</html>
    ''')

@app.route('/api/analyze')
def api_analyze():
    try:
        results = analyzer.analyze_all_stocks()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)})

# Telegram webhook route
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook"""
    try:
        if not telegram_bot:
            return "Telegram bot not configured", 400
            
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            telegram_bot.process_command(message)
        
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

@app.route('/set_webhook')
def set_telegram_webhook():
    """Set up Telegram webhook"""
    if not TELEGRAM_BOT_TOKEN:
        return "Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN environment variable."
    
    # You'll need to update this URL after deployment
    webhook_url = f"https://your-app-name.onrender.com/webhook"
    url = f"{TELEGRAM_API_URL}/setWebhook"
    
    response = requests.post(url, json={'url': webhook_url})
    result = response.json()
    
    if result.get('ok'):
        return f"✅ Webhook set successfully to {webhook_url}"
    else:
        return f"❌ Failed to set webhook: {result.get('description', 'Unknown error')}"

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/advanced')
def advanced_dashboard():
    """Advanced analytics dashboard"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Advanced Analytics - Level 2 Features</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.8em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .header p { font-size: 1.2em; opacity: 0.9; }
        
        .nav-links { text-align: center; margin-bottom: 30px; }
        .nav-link { 
            color: white; 
            text-decoration: none; 
            margin: 0 15px; 
            padding: 10px 20px; 
            border: 2px solid white; 
            border-radius: 25px; 
            transition: all 0.3s;
            display: inline-block;
        }
        .nav-link:hover { background: white; color: #667eea; transform: translateY(-2px); }
        .nav-link.active { background: white; color: #667eea; }
        
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 25px; margin-bottom: 30px; }
        .feature-card { 
            background: rgba(255,255,255,0.95); 
            padding: 25px; 
            border-radius: 15px; 
            text-align: center; 
            transition: transform 0.3s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .feature-card:hover { transform: translateY(-5px); }
        .feature-icon { font-size: 3em; margin-bottom: 15px; }
        .feature-title { font-size: 1.4em; font-weight: bold; margin-bottom: 10px; color: #2c3e50; }
        .feature-desc { color: #666; margin-bottom: 20px; line-height: 1.5; }
        .feature-btn { 
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white; 
            border: none; 
            padding: 12px 24px; 
            border-radius: 25px; 
            font-weight: bold;
            cursor: pointer; 
            transition: all 0.3s;
        }
        .feature-btn:hover { transform: translateY(-2px); }
        
        .stock-search { 
            text-align: center; 
            margin-bottom: 30px; 
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 15px;
        }
        .search-input { 
            padding: 12px; 
            border: 2px solid #ddd; 
            border-radius: 8px; 
            font-size: 16px; 
            margin-right: 10px;
            width: 200px;
        }
        .search-btn { 
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white; 
            border: none; 
            padding: 12px 24px; 
            border-radius: 8px; 
            font-weight: bold;
            cursor: pointer;
        }
        
        .analysis-section { 
            background: rgba(255,255,255,0.95); 
            padding: 25px; 
            border-radius: 15px; 
            margin-bottom: 30px;
            display: none;
        }
        
        .loading { text-align: center; padding: 40px; }
        .spinner { 
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .news-article {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #007bff;
        }
        .article-title { font-weight: bold; margin-bottom: 8px; }
        .article-source { font-size: 12px; color: #666; margin-bottom: 5px; }
        .article-sentiment { 
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            color: white;
            margin-bottom: 8px;
        }
        .sentiment-positive { background: #28a745; }
        .sentiment-negative { background: #dc3545; }
        .sentiment-neutral { background: #6c757d; }
        
        .sector-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .sector-card { 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 10px; 
            border-left: 4px solid #28a745;
        }
        .sector-name { font-weight: bold; margin-bottom: 8px; }
        .sector-perf { font-size: 14px; color: #666; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Advanced Analytics</h1>
            <p>Level 2 Features: News Sentiment • Sector Analysis • Earnings Calendar</p>
        </div>
        
        <div class="nav-links">
            <a href="/" class="nav-link">🏠 Home</a>
            <a href="/portfolio" class="nav-link">📊 Portfolio</a>
            <a href="/watchlist" class="nav-link">📋 Watchlist</a>
            <a href="/advanced" class="nav-link active">🚀 Advanced</a>
        </div>
        
        <div class="stock-search">
            <h3>🔍 Advanced Stock Analysis</h3>
            <input type="text" id="stockSymbol" class="search-input" placeholder="Enter symbol (e.g., AAPL)" maxlength="10">
            <button class="search-btn" onclick="analyzeStock()">🚀 Analyze</button>
        </div>
        
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">📰</div>
                <div class="feature-title">News Sentiment</div>
                <div class="feature-desc">AI-powered analysis of recent news articles to gauge market sentiment for stocks</div>
                <button class="feature-btn" onclick="showInfo('news')">Learn More</button>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">🏭</div>
                <div class="feature-title">Sector Analysis</div>
                <div class="feature-desc">Compare sector performance and identify rotation opportunities across 11 major sectors</div>
                <button class="feature-btn" onclick="showSectorAnalysis()">Analyze Sectors</button>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-title">Earnings Calendar</div>
                <div class="feature-desc">Track upcoming earnings and historical earnings surprises for better timing</div>
                <button class="feature-btn" onclick="showInfo('earnings')">Learn More</button>
            </div>
        </div>
        
        <!-- Analysis Sections -->
        <div class="analysis-section" id="stockAnalysis">
            <h2 id="analysisTitle">📊 Advanced Analysis</h2>
            <div id="analysisContent"></div>
        </div>
        
        <div class="analysis-section" id="sectorAnalysis">
            <h2>🏭 Sector Performance Analysis</h2>
            <div id="sectorContent"></div>
        </div>
    </div>
    
    <script>
        function hideAllSections() {
            document.querySelectorAll('.analysis-section').forEach(section => {
                section.style.display = 'none';
            });
        }
        
        function showSection(sectionId) {
            hideAllSections();
            document.getElementById(sectionId).style.display = 'block';
        }
        
        function analyzeStock() {
            const symbol = document.getElementById('stockSymbol').value.trim().toUpperCase();
            if (!symbol) {
                alert('Please enter a stock symbol');
                return;
            }
            
            showSection('stockAnalysis');
            document.getElementById('analysisTitle').textContent = `🚀 Advanced Analysis: ${symbol}`;
            document.getElementById('analysisContent').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Running advanced analysis for ${symbol}...</p>
                </div>
            `;
            
            fetch(`/api/advanced/${symbol}`)
                .then(response => response.json())
                .then(data => displayAdvancedAnalysis(data))
                .catch(error => {
                    document.getElementById('analysisContent').innerHTML = 
                        `<div style="text-align: center; color: #dc3545;">Error: ${error.message}</div>`;
                });
        }
        
        function displayAdvancedAnalysis(data) {
            let html = '<div style="text-align: center; padding: 20px;">';
            
            if (data.news_sentiment && data.news_sentiment.article_count > 0) {
                const sentiment = data.news_sentiment;
                html += `
                    <div class="news-article">
                        <div class="article-title">📰 News Sentiment Analysis</div>
                        <p><strong>Overall Sentiment:</strong> ${sentiment.overall_sentiment}</p>
                        <p><strong>Confidence:</strong> ${sentiment.confidence}%</p>
                        <p><strong>Articles Analyzed:</strong> ${sentiment.article_count}</p>
                    </div>
                `;
            } else {
                html += '<p>📰 No recent news found for this stock</p>';
            }
            
            if (data.upcoming_earnings && data.upcoming_earnings.has_upcoming) {
                html += `
                    <div class="news-article">
                        <div class="article-title">📊 Upcoming Earnings</div>
                        <p><strong>Next Earnings:</strong> ${data.upcoming_earnings.next_earnings_date}</p>
                        <p><strong>Days Until:</strong> ${data.upcoming_earnings.days_until_earnings}</p>
                    </div>
                `;
            } else {
                html += '<p>📊 No upcoming earnings found</p>';
            }
            
            html += '</div>';
            document.getElementById('analysisContent').innerHTML = html;
        }
        
        function showSectorAnalysis() {
            showSection('sectorAnalysis');
            document.getElementById('sectorContent').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Analyzing sector performance...</p>
                </div>
            `;
            
            fetch('/api/sectors')
                .then(response => response.json())
                .then(data => displaySectorAnalysis(data))
                .catch(error => {
                    document.getElementById('sectorContent').innerHTML = 
                        `<div style="text-align: center; color: #dc3545;">Error: ${error.message}</div>`;
                });
        }
        
        function displaySectorAnalysis(data) {
            let html = '<div class="sector-grid">';
            
            Object.entries(data).forEach(([sector, sectorData]) => {
                const perf3m = sectorData.performance_3m;
                const perfClass = perf3m > 0 ? 'positive' : 'negative';
                
                html += `
                    <div class="sector-card">
                        <div class="sector-name">${sector}</div>
                        <div class="sector-perf">
                            <div>ETF: ${sectorData.etf}</div>
                            <div>3M: <span class="${perfClass}">${perf3m > 0 ? '+' : ''}${perf3m}%</span></div>
                            <div>Volatility: ${sectorData.volatility}%</div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            document.getElementById('sectorContent').innerHTML = html;
        }
        
        function showInfo(type) {
            if (type === 'news') {
                alert('📰 News Sentiment Analysis:\\n\\nEnter a stock symbol above to see AI-powered analysis of recent news articles. The system analyzes headlines and content to determine if news is positive, negative, or neutral for the stock price.');
            } else if (type === 'earnings') {
                alert('📊 Earnings Calendar:\\n\\nEnter a stock symbol above to see upcoming earnings dates and historical earnings surprises. This helps you time your trades around earnings announcements.');
            }
        }
        
        // Allow Enter key in stock search
        document.getElementById('stockSymbol').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                analyzeStock();
            }
        });
    </script>
</body>
</html>
    ''')

@app.route('/api/advanced/<symbol>')
def api_advanced_analysis(symbol):
    """Get advanced analysis for a specific stock"""
    try:
        analysis = advanced_analyzer.get_comprehensive_analysis(symbol.upper())
        analysis['symbol'] = symbol.upper()
        return jsonify(analysis)
    except Exception as e:
        return jsonify({"error": str(e), "symbol": symbol.upper()})

@app.route('/api/sectors')
def api_sector_analysis():
    """Get sector performance analysis"""
    try:
        sector_data = advanced_analyzer.sector_analyzer.get_sector_performance()
        return jsonify(sector_data)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/debug/<symbol>')
def debug_news(symbol):
    """Debug what's happening with news analysis"""
    try:
        # Get raw news first
        news_articles = advanced_analyzer.news_analyzer.get_stock_news(symbol.upper())
        
        debug_info = {
            'symbol': symbol.upper(),
            'articles_found': len(news_articles),
            'articles': []
        }
        
        # Analyze each article manually
        for i, article in enumerate(news_articles[:3]):
            text = f"{article['title']} {article['description']}"
            sentiment = advanced_analyzer.news_analyzer.analyze_sentiment(text)
            
            debug_info['articles'].append({
                'title': article['title'][:100],
                'source': article['source'],
                'sentiment_score': sentiment['score'],
                'sentiment_label': sentiment['label'],
                'text_length': len(text)
            })
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("🚀 Starting Advanced Stock Analysis App")
    print(f"🌐 Running on port {port}")
    if TELEGRAM_BOT_TOKEN:
        print("🤖 Telegram bot configured")
    else:
        print("⚠️  Telegram bot not configured (set TELEGRAM_BOT_TOKEN)")
    
    app.run(debug=debug, host='0.0.0.0', port=port)
