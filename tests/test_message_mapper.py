"""LangGraph 消息映射测试"""

import unittest
from uuid import UUID

from langchain_core.messages import AIMessage, ToolMessage

from app.mappers import message_mapper
from app.routes.api.v1.chat import schemas as chat_schema


class MessageMapperTest(unittest.TestCase):
    """验证接口消息与 LangGraph 消息之间的转换"""

    def test_user_message_metadata_preserves_original_attachments(self) -> None:
        """用户消息持久化后保留原始展示内容和附件"""
        source = chat_schema.MessageSchema(
            role="user",
            parts=[chat_schema.TextContent(text="分析这份数据")],
            attachments=[chat_schema.Attachment(f_path="orders.csv")],
        )

        langchain_message = message_mapper.schema_to_human_message(
            source,
            user_id=1,
            conversation_id=UUID("00000000-0000-0000-0000-000000000002"),
        )
        restored = message_mapper.langchain_message_to_schema(langchain_message)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.message_id, langchain_message.id)
        self.assertEqual(restored.parts, source.parts)
        self.assertEqual(restored.attachments, source.attachments)
        self.assertGreater(len(langchain_message.content), len(source.parts))

    def test_agent_messages_use_langgraph_message_ids(self) -> None:
        """模型和工具消息使用 LangGraph 消息 ID"""
        ai_message = AIMessage(
            id="ai-1",
            content="已完成",
            response_metadata={"finish_reason": "stop"},
        )
        tool_message = ToolMessage(
            id="tool-1",
            content='{"status":"success","f_path":"report.html"}',
            tool_call_id="call-1",
            name="return_file",
        )

        ai_schema = message_mapper.langchain_message_to_schema(ai_message)
        tool_schema = message_mapper.langchain_message_to_schema(tool_message)

        self.assertIsNotNone(ai_schema)
        self.assertIsNotNone(tool_schema)
        assert ai_schema is not None and tool_schema is not None
        self.assertEqual(ai_schema.message_id, "ai-1")
        self.assertEqual(ai_schema.finish_reason, "stop")
        self.assertEqual(tool_schema.message_id, "tool-1")
        self.assertEqual(
            tool_schema.attachments,
            [chat_schema.Attachment(f_path="report.html")],
        )
