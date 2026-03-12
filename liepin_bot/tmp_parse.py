from bs4 import BeautifulSoup
import re

with open('full_page.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print("=== 职位名称 section ===")
# Find the specific job title input context
title_labels = soup.find_all(text=re.compile("职位名称："))
for lbl in title_labels:
    parent = lbl.parent.parent.parent
    if parent:
        print("FOUND BLOCK:")
        print(parent.prettify())

print("\n=== 工作年限 section ===")
# Find work experience
exp_labels = soup.find_all(text=re.compile("工作年限："))
for lbl in exp_labels:
    parent = lbl.parent.parent.parent
    if parent:
        print("FOUND BLOCK:")
        print(parent.prettify())
