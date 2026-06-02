# Define function to fetch top 10 headlines and summaries from each RSS feeds added in config.py file and return as a single text string
import ssl

import feedparser
from config import RSS_FEEDS
import re
import html
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER
import ssl
import gspread
from google.oauth2.service_account import Credentials


def clean_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text.strip()

def fetch_headlines():
    all_headlines = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:  # Fetch top 10 headlines
                all_headlines.append(f"{entry.title}: {clean_html(entry.summary)}")
        except Exception as e:
            print(f"Error fetching from {feed_url}: {e}")
    return "\n".join(all_headlines)


# define a function which takes input as Stock ticker and returns the 60 days historical data with price and volume using yfinance library
def fetch_historical_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        # print (hist)
        # calculate technical indicators like RSI, 20MA, 50MA, average volume
        hist["20MA"] = hist["Close"].rolling(window=20).mean()
        hist["50MA"] = hist["Close"].rolling(window=50).mean()
        delta = hist["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist["RSI"] = 100 - (100 / (1 + rs))
        hist["AvgVolume"] = hist["Volume"].rolling(window=20).mean()
        
        # last 20 days data for Open, Close, High, Low and Volume
        last_20days_data = hist[['Open','Close','High','Low','Volume']].tail(20)
        
        # covert to float and round to 2 decimal places for price columns and int for volume columns
        last_20days_data = last_20days_data.astype({'Open': 'float', 'Close': 'float', 'High': 'float', 'Low': 'float', 'Volume': 'int'}).round({'Open': 2, 'Close': 2, 'High': 2, 'Low': 2})
        
        # add date column to the data
        last_20days_data = last_20days_data.reset_index()
        
        # change the date to string in format YYYY-MM-DD
        last_20days_data['Date'] = last_20days_data['Date'].dt.strftime('%Y-%m-%d')
        
        # remove if volume is 0 for any day in last 20 days data
        last_20days_data = last_20days_data[last_20days_data['Volume'] > 0].copy()
        
        # return a dictionary with current price, 20MA, 50MA, RSI and average volume
        current_price = hist["Close"].iloc[-1]
        return ({"symbol": ticker,
                "current_price": round(float(current_price), 2),
                "pct_change": round(float((current_price - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2] * 100), 2),
                "ma20": round(float(hist["20MA"].iloc[-1]), 2),
                "ma50": round(float(hist["50MA"].iloc[-1]), 2),
                "rsi": round(float(hist["RSI"].iloc[-1]), 2),
                "above_ma20": bool(current_price > hist["20MA"].iloc[-1]),
                "above_ma50": bool(current_price > hist["50MA"].iloc[-1]),
                "volume_today": int(hist["Volume"].iloc[-1]),
                "volume_20_day_avg": int(hist["AvgVolume"].iloc[-1]),
                "volume_spike": bool(hist["Volume"].iloc[-1] > hist["AvgVolume"].iloc[-1] * 1.5),
                "high_52w": round(float(stock.info.get("fiftyTwoWeekHigh", 0)), 2),
                "low_52w": round(float(stock.info.get("fiftyTwoWeekLow", 0)), 2),
                "price_vs_52w_high": round(float((current_price - stock.info.get("fiftyTwoWeekHigh", 0)) / stock.info.get("fiftyTwoWeekHigh", 1) * 100), 2),
                "price_vs_52w_low": round(float((current_price - stock.info.get("fiftyTwoWeekLow", 0)) / stock.info.get("fiftyTwoWeekLow", 1) * 100), 2),
                "last_20days_data": last_20days_data.to_dict(orient="records")
                })
        
    except Exception as e:
        print(f"Error fetching historical data for {ticker}: {e}")
        return None

# define send_email function to send email using smtplib library and email.mime.text library

def send_email(subject, body):
    try:
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        print ("Connecting to email server...")
        # print ("msg", msg.as_string())       

        context = ssl.create_default_context()
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            print("Login successful")
            
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")



# write a function input a list of recommendations - stock symbol, conviction rank, entry price, target, stop loss, date and update the google sheet with the recommendations using gspread library and Google Sheets API

def update_google_sheet(recommendations):
    # This function will update the google sheet with the recommendations
    # define the scope    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)
    
    try:
        # open the google sheet
        sheet = client.open("Claude Agent Portfolio").sheet1
        # update the google sheet with the recommendations
        if not sheet.get_all_values():
            sheet.append_row(["Date", "Symbol", "Conviction Rank", "Entry Price", "Target", "Stop Loss", "Outcome"])
        
        for rec in recommendations:
            sheet.append_row([rec["date"], rec["symbol"], rec["conviction_rank"], rec["entry_price"], rec["target"], rec["stop_loss"], ""])
        print("Google Sheet updated successfully!")
    except Exception as e:
        print(f"Error updating Google Sheet: {e}")
    


# Test the function
if __name__ == "__main__":
    # headlines = fetch_headlines()
    # print(headlines)
    historical_data = fetch_historical_data("RELIANCE.NS")
    print(historical_data)
    # send_email("Test", "<h2>Test email</h2>")
    
    # test update_google_sheet function
    recommendations = [
        {"symbol": "AAPL", "conviction_rank": 1, "entry_price": 150, "target": 170, "stop_loss": 140, "date": "2024-01-01"},
        {"symbol": "MSFT", "conviction_rank": 2, "entry_price": 250, "target": 280, "stop_loss": 230, "date": "2024-01-01"}
    ]
    update_google_sheet(recommendations)
    