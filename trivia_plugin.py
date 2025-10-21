import random
import aiohttp
import yaml
import os
from ncatbot.plugin_system import NcatBotPlugin, event
from ncatbot.plugin_system import command_registry
from ncatbot.plugin_system import filter_registry
from ncatbot.core.event import BaseMessageEvent, PrivateMessageEvent


class TriviaPlugin(NcatBotPlugin):
    name = "TriviaPlugin"
    version = "0.0.1"
    dependencies = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trivia_group = None
        self.api_base_url = "http://localhost:3000/api/v1"
        self.timeout = 30
        self._load_config()

    def _load_config(self):
        """加载配置文件中的API设置"""
        config_path = os.path.join(os.path.dirname(__file__), 'trivia_config.yaml')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if 'trivia_api' in config:
                    self.api_base_url = config['trivia_api'].get('base_url', self.api_base_url)
                    self.timeout = config['trivia_api'].get('timeout', self.timeout)
        except Exception as e:
            print(f"加载配置文件失败: {e}")

    async def on_load(self):
        print(f"插件 {self.name} 加载成功")

    async def on_close(self):
        print(f"插件 {self.name} 卸载成功")

    # 创建冷知识命令组
    trivia_group = command_registry.group("trivia", description="冷知识管理命令")

    # 添加冷知识
    @trivia_group.command("add", description="添加一条冷知识")
    async def add_trivia_cmd(self, event: BaseMessageEvent, *, content: str):
        """添加冷知识"""
        # 从消息中解析标题和内容（简单解析）
        lines = content.split('\n')
        title = lines[0] if lines else "未命名冷知识"
        content_text = '\n'.join(lines[1:]) if len(lines) > 1 else content
        
        try:
            async with aiohttp.ClientSession() as session:
                trivia_data = {
                    "title": title,
                    "content": content_text if content_text else content,
                    "category": "未分类",
                    "author": str(event.sender.user_id) if hasattr(event.sender, 'user_id') else "anonymous"
                }
                
                async with session.post(
                    f"{self.api_base_url}/trivia",
                    json=trivia_data,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await event.reply(f"已添加冷知识，ID: {result['id']}")
                    else:
                        error_text = await response.text()
                        await event.reply(f"添加冷知识失败: {response.status} - {error_text}")
        except Exception as e:
            await event.reply(f"添加冷知识时出错: {str(e)}")

    # 随机获取冷知识
    @trivia_group.command("random", description="随机获取一条冷知识")
    async def random_trivia_cmd(self, event: BaseMessageEvent):
        """随机冷知识"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/trivia/random",
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        reply_text = f"[ID {result['id']}] {result['title']}\n{result['content']}"
                        if 'category' in result:
                            reply_text += f"\n分类: {result['category']}"
                        await event.reply(reply_text)
                    elif response.status == 404:
                        await event.reply("暂无已审核的冷知识")
                    else:
                        error_text = await response.text()
                        await event.reply(f"获取冷知识失败: {response.status} - {error_text}")
        except Exception as e:
            await event.reply(f"获取冷知识时出错: {str(e)}")

    # 根据 ID 查询冷知识
    @trivia_group.command("get", description="根据ID获取冷知识")
    async def get_trivia_cmd(self, event: BaseMessageEvent, trivia_id: str):
        """按ID查询冷知识"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/trivia/{trivia_id}",
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        reply_text = f"[ID {result['id']}] {result['title']}\n{result['content']}"
                        if 'category' in result:
                            reply_text += f"\n分类: {result['category']}"
                        await event.reply(reply_text)
                    elif response.status == 404:
                        await event.reply(f"未找到ID为 {trivia_id} 的冷知识")
                    else:
                        error_text = await response.text()
                        await event.reply(f"获取冷知识失败: {response.status} - {error_text}")
        except Exception as e:
            await event.reply(f"获取冷知识时出错: {str(e)}")