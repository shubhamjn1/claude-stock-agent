# orchestrate the agent
from datetime import datetime

from agent import get_potential_buys, run_agent
from tools import fetch_headlines
from datetime import datetime

print(f"\n=== Stock Agent Running: {datetime.today().strftime('%Y-%m-%d %H:%M')} ===\n")
    

# get the top headlines from the RSS feeds
try:
    headlines = fetch_headlines()
    print("Headlines:", headlines)

    print("Testing stock data fetching and analysis...")
    potential_stocks = get_potential_buys(number_of_stocks=20) 
    print ("Potential Stocks to Buy:", len(potential_stocks))

    # store only the symbols in a list
    filtered_symbols = [stock["symbol"] for stock in potential_stocks] 
    print("Filtered Symbols:", filtered_symbols)

    # run the agent with the filtered symbols and headlines
    if not filtered_symbols:
        print("No stocks passed the filter today. Exiting.")
    run_agent(filtered_symbols, headlines)

except Exception as e:
    print(f"Error in main function: {e}")