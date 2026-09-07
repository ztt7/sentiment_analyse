import asyncio
from typing import Any

from loguru import logger

from engines.common.eventing.bus import subscribe, unsubscribe
from engines.common.eventing.event import EventType
from engines.common.eventing.publishers import publish_host_discussion_message
from engines.contracts.roles import role_display_name
from engines.host_agent.graph import build_graph
from engines.host_agent.judge import Judge
from engines.host_agent.state import Session


class SectionReadyListener:
    """监听章节就绪事件,串行驱动主持人研判图。"""
    # 为什么要把judge对象传到build_graph里面去？本质是build_nodes里面的judge对象是用来做研判的，build_graph里面的2个节点需要调用judge对象的方法来进行研判，所以需要把judge对象传进去。
    # 不同节点要操作同一个judge对象，才能保证研判的一致性和正确性。
    # 我在node.py方法内部用到了外部的对象judge，叫做闭包，闭包是指函数可以访问外部作用域的变量，这样就可以在node.py里面使用judge对象了。

    def __init__(self) -> None:
        """构建主持人、研判图、会话与异步队列工作器。"""
        judge = Judge()
        self.session = Session()
        self.graph = build_graph(judge)
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        """启动事件订阅 + worker;幂等（已激活时no-op)。"""
        # 前端点击按钮后就会被触发，触发后会调用这个方法
        if self._worker is not None:
            return
        # 异步队列
        self._queue = asyncio.Queue()
        subscribe(EventType.SECTION_READY, self._on_callback)
        self._worker = asyncio.create_task(self._run())
        logger.info("SectionReadyListener: 启动, 按章节维度进行主持人研判")

    def stop(self) -> None:
        """停止事件订阅 + 取消 worker"""
        if self._worker is None:
            return
        unsubscribe(self._on_callback)
        self._worker.cancel()
        self._worker = None
        self._queue = None
        self.session.clear()
        logger.info("SectionReadyListener: 已停止")

    def _on_callback(self, _event_type: EventType, payload_data: dict) -> None:
        """事件回调函数,将事件载荷入队等待 worker 串行消费。"""
        self._queue.put_nowait(payload_data)

    async def _run(self) -> None:
        """自旋消费队列,驱动研判图并发布主持人讨论消息。"""
        host_name = role_display_name("host")
        while True:
            section_pack = await self._queue.get()
            try:
                state = self.session.to_state(section_pack)  # 共享session安全
                final_state = await self.graph.ainvoke(state) # await期间并发安全
                self.session.apply_state(final_state)
                discussion_messages = final_state.get("outbox")
            except Exception as exc:
                logger.exception(f"SectionReadyListener: 章节发现处理失败: {exc}")
                continue
            for discussion_message in discussion_messages:
                logger.info(
                    f"【{host_name}】发送讨论消息:"
                    f"来源={role_display_name(discussion_message.source):<12} | "
                    f"章节={discussion_message.section_key:<10} | "
                    f"内容={discussion_message.content[:20]}..."
                )
                # 让前端看到media_agent insight_agent host_agent 他们基于每一个维度说的话
                publish_host_discussion_message(discussion_message)
