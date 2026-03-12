from bs4 import BeautifulSoup
import re

with open('full_page.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

with open('dom_debug.txt', 'w', encoding='utf-8') as out:
    out.write("=== 职位名称 section ===\n")
    # Find the specific job title input context
    title_labels = soup.find_all(string=re.compile("职位名称："))
    for lbl in title_labels:
        parent = lbl.parent.parent.parent
        if parent:
            out.write("FOUND BLOCK:\n")
            out.write(parent.prettify())
            out.write("\n\n")

    out.write("\n=== 工作年限 section ===\n")
    # Find work experience
    exp_labels = soup.find_all(string=re.compile("工作年限：|经验要求："))
    for lbl in exp_labels:
        parent = lbl.parent.parent.parent
        if parent:
            out.write("FOUND BLOCK:\n")
            out.write(parent.prettify())
            out.write("\n\n")
