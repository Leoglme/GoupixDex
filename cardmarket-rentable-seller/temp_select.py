import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(browser={"browser": "firefox", "platform": "windows", "mobile": False})
html = scraper.get('https://www.cardmarket.com/fr/Pokemon/Products/Search?searchString=mega').text
soup = BeautifulSoup(html, 'html.parser')
link = soup.select_one('a[href*="/Products/Singles/"]')
print(link['href'] if link else 'no link')
print(link.get_text(strip=True) if link else 'no text')
