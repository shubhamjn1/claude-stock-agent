from universe import get_universe
from tools import fetch_historical_data, send_email, fetch_headlines, update_google_sheet
from datetime import datetime


# Call get_universe to get the list of stocks
def get_potential_buys(number_of_stocks=50):
    stocks = get_universe()[:number_of_stocks] # Limit to specified number of stocks for testing
    potential_buys = []
    for stock in stocks:
        # print (stock)
        try:
            data = fetch_historical_data(stock)
        except Exception as e:
            print(f"Error fetching data for {stock}: {e}")
            continue
        if data:
            if data["above_ma50"]:
                # store the stock in a list of potential buys
                potential_buys.append(data) 

    print("Potential Buys:", len(potential_buys))
    return potential_buys

# define Tool definition for claude to call fetch_historical_data with stock ticker as input and then decide which stocks to buy based on the output of the tool
tools = [
    {
        "name": "fetch_historical_data",
        "description": "Fetches 60 days of price history and technical indicators for an NSE stock. Returns current price, RSI, 20MA, 50MA, whether price is above moving averages, today's volume vs 20-day average, and volume spike flag. Use this to analyze a stock's technical setup before making a swing trade recommendation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol (e.g., 'RELIANCE.NS')."
                }
            },
            "required": ["ticker"] 
        }
    },
    {
        "name": "send_email",
        "description": "Sends an email with the given subject and body. Use this to send the final stock recommendations to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The subject of the email."
                },
                "body": {
                    "type": "string",
                    "description": "The HTML body content of the email."
                }
            },
            "required": ["subject", "body"]
        }
    },
    {
    "name": "save_recommendations",
    "description": "Save the final stock recommendations to Google Sheets for tracking. Call this BEFORE send_email with structured data for each recommended stock.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "conviction_rank": {"type": "integer"},
                        "entry_price": {"type": "number"},
                        "target": {"type": "number"},
                        "stop_loss": {"type": "number"}
                    },
                    "required": ["symbol", "conviction_rank", "entry_price", "target", "stop_loss"]
                }
            }
        },
        "required": ["recommendations"]
    }
    }
]

SYSTEM_PROMPT = """
You are a senior technical analyst specializing in Indian equity markets (NSE). 
Your job is to identify swing trade buy opportunities from a filtered list of NSE stocks.

You will be given:
- A list of stock symbols that have passed a basic trend filter (price above 50MA)
- Today's top market headlines for context

For each stock you fetch, you will receive:
- Standard indicators: RSI, 20MA, 50MA, volume data
- 52-week high/low and current price position relative to 52-week range
- Last 20 days of OHLCV data for price action analysis

Use the raw price action data to identify patterns such as:
- Trend direction and strength over 20 days
- Support and resistance levels from recent highs/lows
- Candlestick patterns (engulfing, hammer, doji) on recent days
- Volume patterns — accumulation vs distribution
- Price compression or expansion setups


Your process:
1. Use the fetch_stock_data tool to analyze stocks you find interesting — you do not need to fetch all of them, be selective and intelligent about which ones to investigate based on the headlines and your market knowledge
2. Look for stocks with strong technical setups, figure out the exact reason why they are good buys (RSI levels, moving average positions, volume spikes etc.)
3. Cross reference technicals with headlines — a stock with a strong setup AND a positive catalyst is a stronger pick

Rules:
- We are dealing with real money. Only recommend if the data clearly supports it
- If there are no strong setups today, say so clearly — no recommendations is a valid output
- For each recommendation, state the exact technical reason — RSI level, MA position, volume data
- Aim for 3-5 picks maximum, ranked by conviction
- When done with analysis, call send_email with a clean HTML formatted briefing
- Before sending the email, call save_recommendations with structured data for each recommended stock


Swing trade horizon is 5-15 days. Focus on momentum and trend continuation setups.
"""

# define anthropic client
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

print(f"API Key being used: {ANTHROPIC_API_KEY[:20]}...")
client = Anthropic(api_key=ANTHROPIC_API_KEY)


def run_agent(filtered_symbols, headlines):
    messages = [
        {
            "role": "user",
            "content": f"Here are today's filtered stocks: {filtered_symbols}\n\nToday's headlines:\n{headlines}"
        }
    ]
    
    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages
        )
        
        print("\nInitial Response:")
        print(f"Stop Reason: {response.stop_reason}")
        print(f"Content: {response.content}")

        # first append Claude's response to messages
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        
        if response.stop_reason == "tool_use":
            
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    
                    print(f"\nTool Used: {tool_name}")
                    print(f"Tool Input: {tool_input}")
                    
                    if tool_name == "fetch_historical_data":
                        ticker = tool_input["ticker"]
                        results = fetch_historical_data(ticker)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(results)
                        })
                    elif tool_name == "save_recommendations":
                        recommendations = tool_input["recommendations"]
                        # add today's date to each
                        for rec in recommendations:
                            rec["date"] = str(datetime.today().date())
                        update_google_sheet(recommendations)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Recommendations saved to Google Sheets successfully"
                        })
                    elif tool_name == "send_email":
                        subject = tool_input["subject"]
                        body = tool_input["body"]
                        # print(f"\nEmail Subject: {subject}")
                        # print(f"Email Body: {body}")
                        
                        if not body:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "Error: email body was empty, please regenerate the full email"
                            })
                            continue
                        send_email(subject, body)
                        print("Email sent with subject:", subject)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Email sent successfully"
                        })     
                                                           
            
            if not tool_results:
                print("Warning: no tool results generated, breaking")
                break
        
            # then append all tool results to messages
            messages.append({
                "role": "user",
                "content": tool_results
            })
            
            # now exit after email
            if any(block.name == "send_email" for block in response.content if block.type == "tool_use"):
                return

        elif response.stop_reason == "end_turn":
            print("Agent finished.")
            break 

# test 
if __name__ == "__main__":
    print("Testing stock data fetching and analysis...")
    potential_stocks = get_potential_buys(number_of_stocks=20) 
    print ("Potential Stocks to Buy:", len(potential_stocks))
    
    # store only the symbols in a list
    filtered_symbols = [stock["symbol"] for stock in potential_stocks] # limit to 2 for testing
    print("Filtered Symbols:", filtered_symbols)
    
    # get the top headlines from the RSS feeds
    headlines = fetch_headlines()
    print("Headlines:", headlines)
    
    # run the agent with the filtered symbols and headlines
    run_agent(filtered_symbols, headlines)