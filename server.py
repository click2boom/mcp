from dotenv import load_dotenv
from os import getenv
from datetime import datetime
from csv import reader
from pprint import pprint

from httpx import AsyncClient
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP(name="A stdio MCP Server")


@mcp.tool(description="""
得到当前时间
输出格式为: 年-月-日 时:分:秒
""")
def get_current_time() -> str:
  now = datetime.now()
  return now.strftime("%Y-%m-%d %H:%M:%S")



D = {
  'date': '日期',
  'daypower': '白天气压',
  'daytemp': '白天气温',
  'dayweather': '白天天气',
  'daywind': '白天风向',
  'nightpower': '夜间气压',
  'nighttemp': '夜间气温',
  'nightweather': '夜间天气',
  'nightwind': '夜间风向',
  'week': '星期几'
}


@mcp.tool(description="""
得到areaName区域的天气
areaName: **市或者**县
输出格式为: 
  日期:2025-05-12
  星期几:1
  白天天气:晴
  夜间天气:晴
  白天气温:30
  夜间气温:17
  白天风向:北
  夜间风向:南
  白天气压:1-3
  夜间气压:1-3
""".strip())  # 高德地图API
async def get_area_weathear(area_name: str) -> str:
  """
  Args:
  area_name (str): **市或者**县
  Returns:
    (str): 例如
      日期:2025-05-12
      星期几:1
      白天天气:晴
      夜间天气:晴
      白天气温:30
      夜间气温:17
      白天风向:北
      夜间风向:南
      白天气压:1-3
      夜间气压:1-3
  """
  key =getenv('AMAP_API_KEY')
  for area, adcode, citycode in reader(open('area_code.csv')):
    if (area in area_name) or (area_name in area):
      break
  else: return '未再表中找到 {area_name}'
  url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={key}&city={adcode}&extensions=all"
  async with AsyncClient() as client:
    response = await client.get(url)
  print(response.status_code)
  data = response.json()
  days: list = data['forecasts'][0]['casts']
  today = []
  for k, v in days[0].items():
    if k in D:
      today.append(
        f'{D[k]}:{v}'
      )
  return '\n'.join(today)


if __name__ == '__main__':
  print('mcp running ... ')
  mcp.run()
