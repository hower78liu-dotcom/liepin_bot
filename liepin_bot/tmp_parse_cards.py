from bs4 import BeautifulSoup
import re

with open('debug_zero_hits.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print("Looking for possible candidate card classes...")

# Try to find elements with "岁"
age_spans = soup.find_all(string=re.compile(r'\d+岁'))
for age in age_spans:
    parent = age.parent
    print(f"\n--- Found age text: {age.strip()} ---")
    for _ in range(5):
        if parent:
            print(f"Parent classes: {parent.get('class', [])}")
            parent = parent.parent

