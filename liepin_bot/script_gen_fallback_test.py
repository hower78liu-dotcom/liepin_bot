import pandas as pd
import os

# Create dummy search parameters that simulates the fallback test case
data = [
    {
         "职位名称": "资深AI大模型算法架构师(智能体框架与低代码平台方向)",  # this should trigger: 资深AI大模型算法架构师 智能体框架与低代码平台 -> fallback...
         "公司名称": "",
         "工作城市": "北京",
         "经验要求": "5-10年",
         "学历要求": "硕士",
         "年龄要求": "",
    },
    {
         "职位名称": "Python开发工程师(爬虫方向)", 
         "公司名称": "",
         "工作城市": "北京",
         "经验要求": "1-3年",
         "学历要求": "本科",
         "年龄要求": "",
    }
]

df = pd.DataFrame(data)
OUTPUT_FILE = r"D:\ljg\leipin\test_search.xlsx"
df.to_excel(OUTPUT_FILE, index=False)
print(f"✅ Automatically re-generated {OUTPUT_FILE} for fallback logic testing.")
