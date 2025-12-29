import os
from dotenv import load_dotenv
from firecrawl import Firecrawl

load_dotenv()
api_key = os.getenv("FIRECRAWL_API_KEY")
app = Firecrawl(api_key=api_key)

try:
    print("Scraping...")
    data = app.scrape(url="https://example.com", formats=['markdown'])
    print(f"Type: {type(data)}")
    print(f"Dir: {dir(data)}")
    print(f"Data: {data}")
except Exception as e:
    print(f"Error: {e}")
