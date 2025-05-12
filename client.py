from os import getenv
from asyncio import run
from json import dumps, loads
from pprint import pprint
from typing import Optional, Iterable
from contextlib import AsyncExitStack

from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent, ImageContent, EmbeddedResource

from openai import AsyncClient
from openai.types.chat import ChatCompletionToolParam, ChatCompletionToolMessageParam, ChatCompletionUserMessageParam, \
  ChatCompletionMessageParam, ChatCompletionMessage

load_dotenv()  # 从 .env 加载环境变量


class MCPClient:
  def __init__(self):
    # 初始化会话和客户端对象
    self.session: Optional[ClientSession] = None
    self.exit_stack = AsyncExitStack()
    self.openai = AsyncClient(
      api_key=getenv("OPENAI_API_KEY"),
      base_url=getenv("OPENAI_API_BASE_URL")
    )
    self.model = getenv("MODEL")

    self.tools: Optional[list[ChatCompletionToolParam]] = []


  async def connect_to_server(self, server_script_path: str):
    """连接到 MCP 服务器

    Args:
        server_script_path: 服务器脚本的路径 (.py 或 .js)
    """
    is_python = server_script_path.endswith('.py')
    is_js = server_script_path.endswith('.js')
    if not (is_python or is_js):
      raise ValueError("服务器脚本必须是 .py 或 .js 文件")

    command = "python" if is_python else "node"
    server_params = StdioServerParameters(
      command=command,
      args=[server_script_path],
      env=None
    )

    stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
    self.stdio, self.write = stdio_transport
    self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

    await self.session.initialize()

    # 列出可用的工具
    response = await self.session.list_tools()
    print(f"已连接到服务器 工具列表:\n{[tool.name for tool in response.tools]}")
    for tool in response.tools:
      param: ChatCompletionToolParam = {
        "type": "function",
        "function": {
          "name": tool.name,
          "description": getattr(tool, "description", ''),
          'strict': False,
          "parameters": {
            "type": "object",
            "properties": tool.inputSchema['properties'],
            "required": tool.inputSchema.get('required', ''),
          },
        }
      }
      self.tools.append(param)

  async def query_with_tools(self, messages: list[ChatCompletionMessageParam | ChatCompletionMessage]):
    print('请求中(工具调用)...')
    response = await self.openai.chat.completions.create(
      model=self.model,
      messages=[
        {
          "role": "system",
          "content": "You are a helpful assistant with access to tools. You must use these tools to help users accomplish their tasks effectively and efficiently. Always provide clear and concise responses."
        }, *messages
      ],
      tools=self.tools,
    )
 
    # 处理响应并处理工具调用
    text = response.choices[0].message.content \
           or response.choices[0].message.reasoning_content \
           or "无响应"
    assistant_message_content = []
    if response.choices[0].message.tool_calls is None:
      return False, '无工具调用\n' + text
    for tool_call in response.choices[0].message.tool_calls:
      tool_name = tool_call.function.name
      tool_args = loads(tool_call.function.arguments)
      print(f"调用[{tool_name}]中...\n携带参数:")
      pprint(tool_args)

      result: CallToolResult = await self.session.call_tool(
        name=tool_name,
        arguments=tool_args
      )

      if result.isError:
        return False, text + "\n执行调用错误"
      assistant_message_content.append(
        {"call": tool_name, "result": result})
      print(f"Tool [{tool_name}] 已成功调用")

      print('执行返回结果:')
      for content in list(result.content):
        print(type(content), getattr(content, "text", "未获取到text数据"))

      messages.append(response.choices[0].message)
      messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": dumps([
          getattr(content, "text", "")
          for content in list(result.content)
          if getattr(content, "text", "")
        ])
      })
      return True, '已调用工具\n' + text

  async def process_query(self, query: str) -> str:
    """使用 OpenAI 和可用的工具处理查询"""
    messages = [
      {
        "role": "user",
        "content": query
      }
    ]
    ok, error = await self.query_with_tools(messages)
    if not ok:
      return error

    final_text: list[str] = []
    print('再次请求中(附带Tool Call结果)...')
    next_response = await self.openai.chat.completions.create(
      model=self.model,
      messages=[
        {
          "role": "system",
          "content": "You are a helpful assistant with access to tools."
        },
        *messages
      ],
      tools=self.tools
    )
    pprint(next_response.choices[0].message)
    response = next_response.choices[0].message.content \
               or next_response.choices[0].message.reasoning_content \
               or "无响应"

    final_text.append(response)
    return "\n".join(final_text)

  async def chat_loop(self):
    """运行交互式聊天循环"""
    print("\nMCP 客户端已启动!")
    print(f"API_BASE_URL: {getenv('OPENAI_API_BASE_URL')}")
    print(f"MODEL: {getenv('MODEL')}")
    print("输入quit退出")

    while True:
      try:
        query = input("\n: ").strip()

        if query.lower() == 'quit':
          break

        response = await self.process_query(query)
        print("\n" + response.strip())

      except Exception as e:
        print(f"\n- 错误: {str(e)}")

  async def cleanup(self):
    """清理资源"""
    await self.exit_stack.aclose()


async def main():
  if len(argv) < 2:
    print("使用方法: python client.py <MCP Server脚本路径>")
    exit(1)

  client = MCPClient()
  try:
    await client.connect_to_server(argv[1])
    await client.chat_loop()
  finally:
    await client.cleanup()


if __name__ == "__main__":
  from sys import argv

  run(main())
