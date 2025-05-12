# MCP

## 项目介绍

200 行代码实现 MCP Client

没啥好说的
用的都是免费接口

> 使用 OpenAI API 接口

- 硅基流动 LLM API : https://cloud.siliconflow.cn/models?tags=Tools

- 高德地图 天气 API : https://console.amap.com/dev

## 快速启动

```bash
cp example.env .env # 配置自己的API
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt # 安装库
python client.py server.py
```
