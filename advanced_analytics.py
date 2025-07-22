# advanced_analytics.py - Level 2 Advanced Analytics Features
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from textblob import TextBlob
import nltk

# Download required NLTK data (this fixes the sentiment analysis)
try:
    nltk.download('punkt', quiet=True)
    nltk.download('vader_lexicon', quiet=True)
    print("✅ NLTK data downloaded successfully")
except Exception as e:
    print(f"⚠️ NLTK download warning: {e}")
    
import sqlite3
import yfinance as yf
import json
import time
from collections import defaultdict
import re

class NewsAnalyzer:
    """Advanced news sentiment analysis for stocks"""
    
    def __init__(self):
        # Free news APIs (you'll need to get API keys)
        self.newsapi_key = os.environ.get('NEWSAPI_KEY')  # Get free key from newsapi.org
        self.alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_KEY')  # Free from alphavantage.co
        self.init_news_database()
    
    def init_news_database(self):
        """Initialize news storage database"""
        try:
            conn = sqlite3.connect('portfolio.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    title TEXT,
                    description TEXT,
                    url TEXT,
                    published_date TEXT,
                    source TEXT,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    magnitude REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, url)
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ News database initialized")
            
        except Exception as e:
            print(f"❌ Error initializing news database: {e}")
    
    def get_stock_news(self, symbol, days=7):
        """Get recent news for a stock using multiple sources"""
        news_articles = []
        
        # Try NewsAPI first
        if self.newsapi_key:
            news_articles.extend(self._get_newsapi_articles(symbol, days))
        
        # Try Alpha Vantage news
        if self.alpha_vantage_key:
            news_articles.extend(self._get_alpha_vantage_news(symbol))
        
        # Fallback: Yahoo Finance news scraping
        if not news_articles:
            news_articles = self._get_yahoo_news(symbol)
        
        return news_articles
    
    def _get_newsapi_articles(self, symbol, days):
        """Get news from NewsAPI"""
        try:
            # Get company name for better search
            ticker = yf.Ticker(symbol)
            company_name = ticker.info.get('longName', symbol)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': f'"{symbol}" OR "{company_name}"',
                'from': start_date.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'sortBy': 'relevancy',
                'pageSize': 20,
                'language': 'en',
                'apiKey': self.newsapi_key
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            articles = []
            if data.get('status') == 'ok':
                for article in data.get('articles', [])[:10]:  # Limit to 10 most relevant
                    if article['title'] and article['description']:
                        articles.append({
                            'title': article['title'],
                            'description': article['description'],
                            'url': article['url'],
                            'published_date': article['publishedAt'],
                            'source': article['source']['name']
                        })
            
            return articles
            
        except Exception as e:
            print(f"❌ NewsAPI error for {symbol}: {e}")
            return []
    
    def _get_alpha_vantage_news(self, symbol):
        """Get news from Alpha Vantage"""
        try:
            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'apikey': self.alpha_vantage_key,
                'limit': 10
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            articles = []
            if 'feed' in data:
                for item in data['feed'][:10]:
                    articles.append({
                        'title': item.get('title', ''),
                        'description': item.get('summary', ''),
                        'url': item.get('url', ''),
                        'published_date': item.get('time_published', ''),
                        'source': item.get('source', 'Alpha Vantage'),
                        'av_sentiment': item.get('overall_sentiment_score', 0)
                    })
            
            return articles
            
        except Exception as e:
            print(f"❌ Alpha Vantage error for {symbol}: {e}")
            return []
    
    def _get_yahoo_news(self, symbol):
        """Fallback: Get news from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            articles = []
            for item in news[:5]:  # Limit to 5 articles
                articles.append({
                    'title': item.get('title', ''),
                    'description': item.get('summary', ''),
                    'url': item.get('link', ''),
                    'published_date': datetime.fromtimestamp(item.get('providerPublishTime', 0)).isoformat(),
                    'source': item.get('publisher', 'Yahoo Finance')
                })
            
            return articles
            
        except Exception as e:
            print(f"❌ Yahoo Finance news error for {symbol}: {e}")
            return []
    
    def analyze_sentiment(self, text):
        """Analyze sentiment of text using TextBlob"""
        try:
            # Clean the text
            if not text or len(text.strip()) < 5:
                return {'score': 0, 'magnitude': 0, 'label': 'NEUTRAL'}
            
            blob = TextBlob(str(text))
            
            # Get polarity (-1 to 1) and subjectivity (0 to 1)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # Debug print to see what's happening
            print(f"📊 Analyzing: '{text[:50]}...' -> Polarity: {polarity}")
            
            # Convert to label with better thresholds
            if polarity > 0.05:
                label = 'POSITIVE'
            elif polarity < -0.05:
                label = 'NEGATIVE'
            else:
                label = 'NEUTRAL'
            
            return {
                'score': polarity,
                'magnitude': subjectivity,
                'label': label
            }
            
        except Exception as e:
            print(f"❌ Sentiment analysis error: {e}")
            print(f"❌ Text was: {text[:100] if text else 'None'}")
            return {'score': 0, 'magnitude': 0, 'label': 'NEUTRAL'}
    
    def get_stock_sentiment(self, symbol):
        """Get comprehensive sentiment analysis for a stock"""
        try:
            # Get recent news
            articles = self.get_stock_news(symbol)
            
            if not articles:
                return {
                    'overall_sentiment': 'NEUTRAL',
                    'sentiment_score': 0,
                    'confidence': 0,
                    'article_count': 0,
                    'recent_articles': []
                }
            
            # Analyze each article and save to database
            analyzed_articles = []
            sentiment_scores = []
            
            conn = sqlite3.connect('portfolio.db')
            cursor = conn.cursor()
            
            for article in articles:
                # Combine title and description for analysis
                text = f"{article['title']} {article['description']}"
                sentiment = self.analyze_sentiment(text)
                
                # Save to database
                cursor.execute('''
                    INSERT OR REPLACE INTO news_sentiment 
                    (symbol, title, description, url, published_date, source, 
                     sentiment_score, sentiment_label, magnitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, article['title'], article['description'], article['url'],
                    article['published_date'], article['source'],
                    sentiment['score'], sentiment['label'], sentiment['magnitude']
                ))
                
                analyzed_articles.append({
                    **article,
                    'sentiment': sentiment
                })
                sentiment_scores.append(sentiment['score'])
            
            conn.commit()
            conn.close()
            
            # Calculate overall sentiment
            if sentiment_scores:
                avg_sentiment = np.mean(sentiment_scores)
                confidence = min(100, len(sentiment_scores) * 10)  # More articles = higher confidence
                
                if avg_sentiment > 0.15:
                    overall_sentiment = 'VERY POSITIVE'
                elif avg_sentiment > 0.05:
                    overall_sentiment = 'POSITIVE'
                elif avg_sentiment < -0.15:
                    overall_sentiment = 'VERY NEGATIVE'
                elif avg_sentiment < -0.05:
                    overall_sentiment = 'NEGATIVE'
                else:
                    overall_sentiment = 'NEUTRAL'
            else:
                avg_sentiment = 0
                overall_sentiment = 'NEUTRAL'
                confidence = 0
            
            return {
                'overall_sentiment': overall_sentiment,
                'sentiment_score': round(avg_sentiment, 3),
                'confidence': confidence,
                'article_count': len(articles),
                'recent_articles': analyzed_articles[:5]  # Return top 5 for display
            }
            
        except Exception as e:
            print(f"❌ Error getting sentiment for {symbol}: {e}")
            return {
                'overall_sentiment': 'NEUTRAL',
                'sentiment_score': 0,
                'confidence': 0,
                'article_count': 0,
                'recent_articles': []
            }


class SectorAnalyzer:
    """Sector comparison and analysis"""
    
    def __init__(self):
        self.sector_etfs = {
            'Technology': 'XLK',
            'Healthcare': 'XLV', 
            'Financial Services': 'XLF',
            'Consumer Discretionary': 'XLY',
            'Communication Services': 'XLC',
            'Industrials': 'XLI',
            'Consumer Defensive': 'XLP',
            'Energy': 'XLE',
            'Utilities': 'XLU',
            'Real Estate': 'XLRE',
            'Materials': 'XLB'
        }
        self.init_sector_database()
    
    def init_sector_database(self):
        """Initialize sector analysis database"""
        try:
            conn = sqlite3.connect('portfolio.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sector_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    sector TEXT,
                    performance_1d REAL,
                    performance_1w REAL,
                    performance_1m REAL,
                    performance_3m REAL,
                    volatility REAL,
                    relative_strength REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, sector)
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Sector database initialized")
            
        except Exception as e:
            print(f"❌ Error initializing sector database: {e}")
    
    def get_sector_performance(self):
        """Analyze performance of all sectors"""
        try:
            sector_data = {}
            
            for sector, etf in self.sector_etfs.items():
                print(f"📊 Analyzing {sector} sector ({etf})...")
                
                # Get ETF data
                ticker = yf.Ticker(etf)
                df = ticker.history(period="3mo")
                
                if df.empty:
                    continue
                
                # Calculate performance metrics
                current_price = df['Close'].iloc[-1]
                
                # Performance calculations
                perf_1d = ((current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100) if len(df) >= 2 else 0
                perf_1w = ((current_price - df['Close'].iloc[-5]) / df['Close'].iloc[-5] * 100) if len(df) >= 5 else 0
                perf_1m = ((current_price - df['Close'].iloc[-22]) / df['Close'].iloc[-22] * 100) if len(df) >= 22 else 0
                perf_3m = ((current_price - df['Close'].iloc[0]) / df['Close'].iloc[0] * 100)
                
                # Volatility (20-day)
                returns = df['Close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252) * 100  # Annualized
                
                # Relative strength vs S&P 500
                spy = yf.Ticker("SPY")
                spy_df = spy.history(period="3mo")
                if not spy_df.empty:
                    spy_return = (spy_df['Close'].iloc[-1] - spy_df['Close'].iloc[0]) / spy_df['Close'].iloc[0] * 100
                    relative_strength = perf_3m - spy_return
                else:
                    relative_strength = 0
                
                sector_data[sector] = {
                    'etf': etf,
                    'current_price': round(current_price, 2),
                    'performance_1d': round(perf_1d, 2),
                    'performance_1w': round(perf_1w, 2),
                    'performance_1m': round(perf_1m, 2),
                    'performance_3m': round(perf_3m, 2),
                    'volatility': round(volatility, 2),
                    'relative_strength': round(relative_strength, 2)
                }
                
                # Save to database
                self._save_sector_data(sector, sector_data[sector])
                
                time.sleep(0.1)  # Rate limiting
            
            return sector_data
            
        except Exception as e:
            print(f"❌ Error in sector analysis: {e}")
            return {}
    
    def _save_sector_data(self, sector, data):
        """Save sector data to database"""
        try:
            conn = sqlite3.connect('portfolio.db')
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                INSERT OR REPLACE INTO sector_analysis 
                (date, sector, performance_1d, performance_1w, performance_1m, 
                 performance_3m, volatility, relative_strength)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, sector, data['performance_1d'], data['performance_1w'],
                data['performance_1m'], data['performance_3m'],
                data['volatility'], data['relative_strength']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error saving sector data: {e}")


class EarningsAnalyzer:
    """Earnings calendar and analysis"""
    
    def __init__(self):
        self.alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_KEY')
        self.init_earnings_database()
    
    def init_earnings_database(self):
        """Initialize earnings database"""
        try:
            conn = sqlite3.connect('portfolio.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS earnings_calendar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    earnings_date TEXT,
                    fiscal_quarter TEXT,
                    estimated_eps REAL,
                    reported_eps REAL,
                    surprise_percent REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, earnings_date)
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Earnings database initialized")
            
        except Exception as e:
            print(f"❌ Error initializing earnings database: {e}")
    
    def get_upcoming_earnings(self, symbol):
        """Get upcoming earnings for a stock"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Try to get earnings calendar from yfinance
            calendar = ticker.calendar
            
            if calendar is not None and not calendar.empty:
                next_earnings = calendar.index[0]
                
                return {
                    'has_upcoming': True,
                    'next_earnings_date': next_earnings.strftime('%Y-%m-%d'),
                    'days_until_earnings': (next_earnings - datetime.now()).days
                }
            
            return {'has_upcoming': False}
            
        except Exception as e:
            print(f"❌ Error getting earnings for {symbol}: {e}")
            return {'has_upcoming': False}
    
    def get_earnings_history(self, symbol):
        """Get historical earnings data"""
        try:
            ticker = yf.Ticker(symbol)
            earnings = ticker.earnings_dates
            
            if earnings is not None and not earnings.empty:
                recent_earnings = earnings.head(8)  # Last 8 quarters
                
                history = []
                for date, row in recent_earnings.iterrows():
                    eps_estimate = row.get('EPS Estimate', 0)
                    eps_actual = row.get('Reported EPS', 0)
                    
                    if pd.notna(eps_estimate) and pd.notna(eps_actual) and eps_estimate != 0:
                        surprise = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100
                    else:
                        surprise = 0
                    
                    history.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'estimated_eps': round(eps_estimate, 2) if pd.notna(eps_estimate) else 0,
                        'actual_eps': round(eps_actual, 2) if pd.notna(eps_actual) else 0,
                        'surprise_percent': round(surprise, 1)
                    })
                
                return history
            
            return []
            
        except Exception as e:
            print(f"❌ Error getting earnings history for {symbol}: {e}")
            return []


class AdvancedAnalyzer:
    """Main class that combines all advanced analytics"""
    
    def __init__(self):
        self.news_analyzer = NewsAnalyzer()
        self.sector_analyzer = SectorAnalyzer()
        self.earnings_analyzer = EarningsAnalyzer()
        print("🚀 Advanced Analytics initialized")
    
    def get_comprehensive_analysis(self, symbol):
        """Get comprehensive analysis including all advanced features"""
        try:
            print(f"🔍 Running advanced analysis for {symbol}...")
            
            analysis = {}
            
            # News sentiment analysis
            print(f"📰 Analyzing news sentiment for {symbol}...")
            analysis['news_sentiment'] = self.news_analyzer.get_stock_sentiment(symbol)
            
            # Earnings information
            print(f"📊 Getting earnings data for {symbol}...")
            analysis['upcoming_earnings'] = self.earnings_analyzer.get_upcoming_earnings(symbol)
            analysis['earnings_history'] = self.earnings_analyzer.get_earnings_history(symbol)
            
            # Sector comparison will be added when we have stock performance data
            analysis['sector_comparison'] = None
            
            return analysis
            
        except Exception as e:
            print(f"❌ Error in comprehensive analysis for {symbol}: {e}")
            return {
                'news_sentiment': {'overall_sentiment': 'NEUTRAL', 'sentiment_score': 0, 'confidence': 0, 'article_count': 0},
                'upcoming_earnings': {'has_upcoming': False},
                'earnings_history': [],
                'sector_comparison': None
            }
    
    def get_market_overview(self):
        """Get overall market analysis"""
        try:
            print("🌍 Generating market overview...")
            
            # Sector analysis
            sector_data = self.sector_analyzer.get_sector_performance()
            
            overview = {
                'sector_data': sector_data,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            return overview
            
        except Exception as e:
            print(f"❌ Error generating market overview: {e}")
            return {'sector_data': {}, 'analysis_timestamp': datetime.now().isoformat()}


# Example usage and testing functions
def test_advanced_analytics():
    """Test the advanced analytics features"""
    analyzer = AdvancedAnalyzer()
    
    # Test with popular stocks
    test_symbols = ['AAPL', 'GOOGL', 'TSLA']
    
    for symbol in test_symbols:
        print(f"\n{'='*50}")
        print(f"Testing Advanced Analytics for {symbol}")
        print('='*50)
        
        analysis = analyzer.get_comprehensive_analysis(symbol)
        
        # Display results
        print(f"\n📰 News Sentiment: {analysis['news_sentiment']['overall_sentiment']}")
        print(f"📊 Sentiment Score: {analysis['news_sentiment']['sentiment_score']}")
        print(f"📈 Article Count: {analysis['news_sentiment']['article_count']}")
        
        if analysis['upcoming_earnings']['has_upcoming']:
            print(f"📅 Next Earnings: {analysis['upcoming_earnings']['next_earnings_date']}")
        else:
            print("📅 No upcoming earnings found")
        
        print(f"📜 Earnings History: {len(analysis['earnings_history'])} quarters available")

if __name__ == "__main__":
    test_advanced_analytics()
