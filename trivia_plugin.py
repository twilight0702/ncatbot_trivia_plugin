import aiohttp
import yaml
import os
import shlex

from ncatbot.core import GroupMessageEvent
from ncatbot.plugin_system import NcatBotPlugin
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

    async def trivia_command_filter(self, event: BaseMessageEvent):
        """处理 /trivia 开头的命令，根据第二个词分发到不同处理函数"""
        raw_msg = event.raw_message.strip()
        
        # 检查是否以 /trivia 开头
        if not raw_msg.startswith("/trivia"):
            return
            
        # 分割命令
        parts = raw_msg.split(" ", 2)
        if len(parts) >= 2:
            subcommand = parts[1]
            
            # 根据子命令分发到不同处理函数
            if subcommand == "add":
                await self.handle_trivia_add(event, parts)
            elif subcommand == "random":
                await self.handle_trivia_random(event, parts)
            elif subcommand == "get":
                await self.handle_trivia_get(event, parts)
            elif subcommand == "help":
                await self.handle_trivia_help(event)
            else:
                await event.reply(f"未知的子命令: {subcommand}。支持的命令: add, random, get, help")
        else:
            # 只有 /trivia，显示帮助信息
            await self.handle_trivia_help(event)

    async def handle_trivia_add(self, event: BaseMessageEvent, parts: list):
        print("添加冷知识命令被调用")

        raw_msg = event.raw_message.strip()
        parts = raw_msg.split(" ", 2)
        if len(parts) < 3:
            await event.reply("命令格式错误，请使用：/trivia add -t <标题> -c <内容> [-g <分类>] [-a <作者>]")
            return

        arg_str = parts[2]

        # 安全拆分命令，支持带引号的参数
        try:
            tokens = shlex.split(arg_str)
        except Exception as e:
            await event.reply(f"解析参数失败: {str(e)}")
            return

        # 定义支持的参数
        arg_map = {
            "-t": "title",
            "--title": "title",
            "-c": "content",
            "--content": "content",
            "-g": "category",
            "--category": "category",
            "-a": "author",
            "--author": "author"
        }

        # 存储解析结果
        parsed_args = {}
        i = 0
        while i < len(tokens):
            key = tokens[i]
            if key in arg_map and i + 1 < len(tokens):
                parsed_args[arg_map[key]] = tokens[i + 1]
                i += 2
            else:
                i += 1

        # 检查必填字段
        title = parsed_args.get("title")
        content = parsed_args.get("content")
        if not title or not content:
            await event.reply("标题和内容不能为空，请使用：/trivia add -t <标题> -c <内容> [-g <分类>] [-a <作者>]")
            return

        category = parsed_args.get("category", "未分类")
        author = parsed_args.get("author") or (str(event.sender.user_id) if hasattr(event.sender, 'user_id') else "anonymous")

        trivia_data = {
            "title": title,
            "content": content,
            "category": category,
            "author": author
        }

        print(f"添加冷知识数据: {trivia_data}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_base_url}/trivia",
                        json=trivia_data,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200 or response.status == 201:
                        result = await response.json()
                        await event.reply(f"已添加冷知识，ID: {result['id']}，等待审核")
                    else:
                        error_text = await response.text()
                        await event.reply(f"添加冷知识失败: {response.status} - {error_text}")
        except Exception as e:
            await event.reply(f"添加冷知识时出错: {str(e)}")

    async def handle_trivia_random(self, event: BaseMessageEvent, parts: list):
        """处理 /trivia random 命令"""
        # 解析可选参数
        category = None
        if len(parts) >= 3:
            arg_str = parts[2]
            try:
                tokens = shlex.split(arg_str)
                i = 0
                while i < len(tokens):
                    if tokens[i] in ("-C", "--category") and i + 1 < len(tokens):
                        category = tokens[i + 1]
                        break
                    else:
                        i += 1
            except Exception as e:
                await event.reply(f"解析参数失败: {str(e)}")
                return

        # 构建请求URL
        url = f"{self.api_base_url}/trivia/random"
        if category:
            url += f"?category={category}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        reply_text = f"[ID {result['id']}] {result['title']}\n{result['content']}"
                        if 'category' in result:
                            reply_text += f"\n分类: {result['category']}"
                        await event.reply(reply_text)
                    elif response.status == 404:
                        if category:
                            await event.reply(f"暂无分类为 {category} 的已审核冷知识")
                        else:
                            await event.reply("暂无已审核的冷知识")
                    else:
                        error_text = await response.text()
                        await event.reply(f"获取冷知识失败: {response.status} - {error_text}")
        except Exception as e:
            await event.reply(f"获取冷知识时出错: {str(e)}")

    async def handle_trivia_get(self, event: BaseMessageEvent, parts: list):
        """处理 /trivia get <id> 命令"""
        # 解析参数
        trivia_id = None
        if len(parts) >= 3:
            arg_str = parts[2]
            try:
                tokens = shlex.split(arg_str)
                # 查找 -i 或 --id 参数
                i = 0
                while i < len(tokens):
                    if tokens[i] in ("-i", "--id") and i + 1 < len(tokens):
                        trivia_id = tokens[i + 1]
                        break
                    else:
                        # 如果没有参数标志，假设第一个参数就是ID
                        if not trivia_id and not tokens[i].startswith("-"):
                            trivia_id = tokens[i]
                        i += 1
            except Exception as e:
                await event.reply(f"解析参数失败: {str(e)}")
                return
        else:
            await event.reply("命令格式错误，请使用：/trivia get <ID>")
            return

        if not trivia_id:
            await event.reply("请提供冷知识的ID，使用：/trivia get <ID> 或 /trivia get --id <ID>")
            return

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

    async def handle_trivia_help(self, event: BaseMessageEvent):
        """处理 /trivia 帮助信息"""
        help_text = """冷知识插件使用说明：
/trivia add -t <标题> -c <内容> [-g <分类>] [-a <作者>]  - 添加冷知识
/trivia add --title <标题> --content <内容> [--category <分类>] [--author <作者>]
/trivia random [-g <分类>]  - 随机获取一条冷知识
/trivia random [--category <分类>]
/trivia get <ID>  - 根据ID获取冷知识
/trivia get -i <ID>
/trivia get --id <ID>"""
        await event.reply(help_text)


    @filter_registry.private_filter
    async def trivia_cmd(self, event: PrivateMessageEvent):
        print("收到私聊消息")
        await self.trivia_command_filter(event)

    @filter_registry.group_filter
    async def trivia_cmd(self, event: GroupMessageEvent):
        print("收到群消息")
        await self.trivia_command_filter(event)