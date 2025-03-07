# 本程序获得全国所有火车站的站名和其电报码的对应关系，如“上海虹桥”站的电报码为“AOH”
import requests
import json
import pandas as pd
# 下面的url可以获得所有火车站的名字和电报码
url = 'https://www.12306.cn/index/otn/index12306/queryAllCacheSaleTime'
content = requests.get(url=url).json()
# 保存火车站代码文件为JSON格式
with open('station_code.txt', 'w', encoding='utf-8') as f:
    json.dump(content['data'], f, ensure_ascii=False, indent=4)

content_list = pd.json_normalize(content['data'], errors='ignore')
content_list.to_excel("station_code.xlsx", index=False) # 保存火车站代码文件为xlsx格式，所以和JSON格式一起共有2种格式，多种格式只是为了好看而已
rows = content_list.shape[0]
print(rows)

