# 📊 Advanced Stock Analysis App

A professional-grade stock analysis application with probability ranges, risk-adjusted returns, and Telegram bot integration.

## 🚀 Features

- **Advanced Analysis**: 20 popular stocks with comprehensive technical indicators
- **Probability Ranges**: 1 week, 1 month, and 3 month predictions with confidence intervals
- **Risk-Adjusted Returns**: Sharpe, Sortino, and Calmar ratios
- **Relative Performance**: Compare stocks against S&P 500 benchmark
- **Telegram Bot**: Get analysis via Telegram commands
- **Professional UI**: Clean, responsive web interface

## 📈 Technical Indicators

- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Moving Averages (20, 50, 200 day)
- Bollinger Bands
- Volume Analysis
- Volatility Metrics

## 🤖 Telegram Bot Commands

- `/start` - Welcome message and help
- `/analyze` - Full analysis of all stocks
- `/stock SYMBOL` - Analyze specific stock (e.g., `/stock AAPL`)
- `/top` - Get top 5 buy signals
- `/help` - Show available commands

## 🔧 Setup for Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd stock-analysis-app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables** (optional)
   ```bash
   export TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   export FLASK_ENV=development
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   - Web interface: `http://localhost:5000`
   - Health check: `http://localhost:5000/health`

## 🚀 Deployment

This application is configured for deployment on Render.com:

1. **Build Command**: `pip install -r requirements.txt`
2. **Start Command**: `python app.py`
3. **Environment Variables**:
   - `TELEGRAM_BOT_TOKEN` (optional, for Telegram bot)
   - `PORT` (automatically set by Render)

## 📊 Analysis Methodology

### Signal Generation
- **Strong Buy**: High confidence bullish signals across multiple indicators
- **Buy**: Moderate bullish signals
- **Hold**: Mixed or neutral signals
- **Sell**: Moderate bearish signals
- **Strong Sell**: High confidence bearish signals

### Probability Ranges
- **68% Confidence**: 1 standard deviation (likely range)
- **95% Confidence**: 2 standard deviations (very likely range)
- Based on historical volatility and return patterns

### Risk Metrics
- **Sharpe Ratio**: Return per unit of total risk
- **Sortino Ratio**: Return per unit of downside risk
- **Calmar Ratio**: Return per unit of maximum drawdown
- **Beta**: Sensitivity to market movements
- **Alpha**: Excess return above expected

## 📱 Telegram Bot Setup

1. **Create a bot** with @BotFather on Telegram
2. **Get the token** and set it as `TELEGRAM_BOT_TOKEN` environment variable
3. **Set webhook** by visiting `/set_webhook` endpoint after deployment
4. **Start chatting** with your bot!

## 🛠️ Technical Stack

- **Backend**: Flask (Python)
- **Data**: Yahoo Finance API (yfinance)
- **Analysis**: pandas, NumPy, scikit-learn
- **Deployment**: Render.com
- **Bot**: Telegram Bot API

## 📝 License

This project is for educational purposes. Please ensure compliance with data provider terms of service.

## 🤝 Contributing

Feel free to submit issues and pull requests to improve the application.

## ⚠️ Disclaimer

This application is for informational purposes only. It does not constitute financial advice. Always do your own research before making investment decisions.
