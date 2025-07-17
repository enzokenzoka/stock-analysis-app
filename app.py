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
warnings.filterwarnings('ignore')

app = Flask(__name__)

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

class AdvancedStockAnalyzer:
    def __init__(self):
        # Extended stock list for more comprehensive analysis
        self.stock_list = [
            'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'META', 'NVDA', 'NFLX',
            'UBER', 'SNAP', 'ZOOM', 'PLTR', 'COIN', 'RBLX', 'SHOP', 'SQ',
            'PYPL', 'ADBE', 'CRM', 'SPOT'
        ]
        
        # Get market benchmark data (S&P 500)
        self.market_data = None
        self.risk_free_rate = 0.045  # Current 3-month Treasury rate (~4.5%)
        
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
        """Calculate probability ranges for different time horizons"""
        try:
            current_price = df['close'].iloc[-1]
            returns = df['returns'].dropna()
            
            # Calculate statistics
            mean_return = returns.mean()
            std_return = returns.std()
            
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
                # 68% confidence interval (1 standard deviation)
                prob_68_low = current_price * (1 + horizon_mean - horizon_std)
                prob_68_high = current_price * (1 + horizon_mean + horizon_std)
                
                # 95% confidence interval (2 standard deviations)
                prob_95_low = current_price * (1 + horizon_mean - 2*horizon_std)
                prob_95_high = current_price * (1 + horizon_mean + 2*horizon_std)
                
                probability_ranges[period] = {
                    'expected_price': current_price * (1 + horizon_mean),
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
        """Calculate risk-adjusted return metrics"""
        try:
            returns = df['returns'].dropna()
            
            # Annualized metrics
            annual_return = returns.mean() * 252
            annual_volatility = returns.std() * np.sqrt(252)
            
            # Sharpe Ratio
            excess_return = annual_return - self.risk_free_rate
            sharpe_ratio = excess_return / annual_volatility if annual_volatility > 0 else 0
            
            # Sortino Ratio (downside deviation)
            negative_returns = returns[returns < 0]
            downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
            sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
            
            # Maximum Drawdown
            cumulative_returns = (1 + returns).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - rolling_max) / rolling_max
            max_drawdown = drawdown.min()
            
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
            return None
    
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
        """Generate trading signal based on multiple factors"""
        try:
            latest = df.iloc[-1]
            
            # Technical signals
            signals = []
            strength = 0
            
            # RSI signal
            if latest['rsi'] < 30:
                signals.append("Oversold (RSI < 30)")
                strength += 3
            elif latest['rsi'] > 70:
                signals.append("Overbought (RSI > 70)")
                strength -= 3
            
            # Moving average signals
            if latest['close'] > latest['ma_20'] > latest['ma_50']:
                signals.append("Strong uptrend")
                strength += 2
            elif latest['close'] < latest['ma_20'] < latest['ma_50']:
                signals.append("Strong downtrend")
                strength -= 2
            
            # MACD signal
            if latest['macd'] > latest['macd_signal']:
                signals.append("Positive momentum")
                strength += 1
            else:
                signals.append("Negative momentum")
                strength -= 1
            
            # Bollinger Bands
            if latest['close'] < latest['bb_lower']:
                signals.append("Below lower Bollinger Band")
                strength += 1
            elif latest['close'] > latest['bb_upper']:
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
            return None
    
    def analyze_stock(self, symbol):
        """Complete analysis of a single stock"""
        print(f"📊 Analyzing {symbol}...")
        
        # Get data
        df = self.get_stock_data(symbol)
        if df is None:
            return None
        
        # Calculate indicators
        df = self.calculate_technical_indicators(df)
        if df is None:
            return None
        
        # Get latest values
        latest = df.iloc[-1]
        
        # Calculate all metrics
        probability_ranges = self.calculate_probability_ranges(df)
        risk_metrics = self.calculate_risk_metrics(df)
        relative_performance = self.calculate_relative_performance(df)
        signal_data = self.generate_signal(df)
        
        # Compile results
        result = {
            'symbol': symbol,
            'current_price': round(float(latest['close']), 2),
            'signal': signal_data['signal'] if signal_data else 'HOLD',
            'confidence': signal_data['confidence'] if signal_data else 50,
            'rsi': round(float(latest['rsi']), 1),
            'volume': int(latest['volume']),
            'volatility': round(float(latest['volatility']), 1),
            
            # Probability ranges
            'probability_ranges': probability_ranges,
            
            # Risk metrics
            'risk_metrics': risk_metrics,
            
            # Relative performance
            'relative_performance': relative_performance,
            
            # Technical details
            'technical_details': {
                'ma_20': round(float(latest['ma_20']), 2),
                'ma_50': round(float(latest['ma_50']), 2),
                'ma_200': round(float(latest['ma_200']), 2),
                'macd': round(float(latest['macd']), 3),
                'bb_position': round(((latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])) * 100, 1),
                'reasons': signal_data['reasons'] if signal_data else []
            }
        }
        
        return result
    
    def analyze_all_stocks(self):
        """Analyze all stocks in the watchlist"""
        print("🚀 Starting Advanced Stock Analysis...")
        
        # Load market data first
        self.get_market_data()
        
        results = []
        failed_stocks = []
        
        for i, symbol in enumerate(self.stock_list, 1):
            print(f"\n📊 Progress: {i}/{len(self.stock_list)} - {symbol}")
            
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Advanced Stock Analysis</h1>
            <p>Probability ranges • Risk-adjusted returns • Relative performance</p>
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
    `;
    
    gridDiv.appendChild(card);
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
