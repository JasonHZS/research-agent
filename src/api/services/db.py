"""SQLite database service for conversation persistence."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


# Use declarative_base() for SQLAlchemy 1.4 compatibility
Base = declarative_base()


class ConversationModel(Base):
    """SQLAlchemy model for conversations."""

    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, default="New Conversation")
    model_provider = Column(String(50), nullable=False, default="aliyun")
    model_name = Column(String(100), nullable=False, default="qwen-max")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Use lazy="raise" to prevent implicit lazy loading in async context
    messages = relationship(
        "MessageModel", back_populates="conversation", cascade="all, delete-orphan", lazy="raise"
    )
    
    # Non-ORM attribute for holding loaded messages
    _loaded_messages: list = None


class MessageModel(Base):
    """SQLAlchemy model for messages."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uix_conversation_sequence"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, default=list)  # List of tool call objects
    created_at = Column(DateTime, default=datetime.now)
    sequence = Column(Integer, nullable=False)  # Order within conversation

    conversation = relationship("ConversationModel", back_populates="messages")


# Global engine and session factory
_engine = None
_async_session_factory = None


async def init_database(db_path: str = "data/research_agent.db") -> None:
    """Initialize the database and create tables."""
    global _engine, _async_session_factory

    # Ensure data directory exists
    import os

    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    # Create async engine
    _engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )

    # Create tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory (SQLAlchemy 1.4 compatible)
    _async_session_factory = sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )


def get_session() -> AsyncSession:
    """Get a new database session."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _async_session_factory()


class ConversationStore:
    """Service for managing conversations and messages."""

    async def create_conversation(
        self,
        title: Optional[str] = None,
        model_provider: str = "aliyun",
        model_name: str = "qwen-max",
    ) -> ConversationModel:
        """Create a new conversation."""
        async with get_session() as session:
            conversation = ConversationModel(
                id=str(uuid.uuid4()),
                title=title or "New Conversation",
                model_provider=model_provider,
                model_name=model_name,
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationModel]:
        """Get a conversation by ID with its messages."""
        async with get_session() as session:
            result = await session.execute(
                select(ConversationModel).where(ConversationModel.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                # Load messages separately to avoid lazy loading issues
                messages_result = await session.execute(
                    select(MessageModel)
                    .where(MessageModel.conversation_id == conversation_id)
                    .order_by(MessageModel.sequence)
                )
                # Store in non-ORM attribute to avoid triggering relationship
                conversation._loaded_messages = list(messages_result.scalars().all())
            return conversation

    async def list_conversations(self) -> list[ConversationModel]:
        """List all conversations ordered by update time."""
        async with get_session() as session:
            result = await session.execute(
                select(ConversationModel).order_by(ConversationModel.updated_at.desc())
            )
            conversations = list(result.scalars().all())

            if not conversations:
                return conversations

            conversation_ids = [conv.id for conv in conversations]
            counts_result = await session.execute(
                select(MessageModel.conversation_id, func.count(MessageModel.id))
                .where(MessageModel.conversation_id.in_(conversation_ids))
                .group_by(MessageModel.conversation_id)
            )
            counts_map = {conv_id: count for conv_id, count in counts_result.all()}

            for conv in conversations:
                conv.message_count = counts_map.get(conv.id, 0)

            return conversations

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        async with get_session() as session:
            result = await session.execute(
                select(ConversationModel).where(ConversationModel.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                await session.delete(conversation)
                await session.commit()
                return True
            return False

    async def update_conversation_title(
        self, conversation_id: str, title: str
    ) -> Optional[ConversationModel]:
        """Update conversation title."""
        async with get_session() as session:
            result = await session.execute(
                select(ConversationModel).where(ConversationModel.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                conversation.title = title
                conversation.updated_at = datetime.now()
                await session.commit()
                await session.refresh(conversation)
            return conversation

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list] = None,
    ) -> MessageModel:
        """Add a message to a conversation."""
        async with get_session() as session:
            # Get next sequence number atomically in the database
            result = await session.execute(
                select(func.coalesce(func.max(MessageModel.sequence), -1)).where(
                    MessageModel.conversation_id == conversation_id
                )
            )
            sequence = result.scalar_one() + 1

            message = MessageModel(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                role=role,
                content=content,
                tool_calls=tool_calls or [],
                sequence=sequence,
            )
            session.add(message)

            # Update conversation timestamp
            conv_result = await session.execute(
                select(ConversationModel).where(ConversationModel.id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            if conversation:
                conversation.updated_at = datetime.now()
                # Auto-generate title from first user message
                if sequence == 0 and role == "user":
                    conversation.title = content[:50] + ("..." if len(content) > 50 else "")

            await session.commit()
            await session.refresh(message)
            return message

    async def get_messages(self, conversation_id: str) -> list[MessageModel]:
        """Get all messages for a conversation."""
        async with get_session() as session:
            result = await session.execute(
                select(MessageModel)
                .where(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.sequence)
            )
            return list(result.scalars().all())


# Singleton instance
_conversation_store: Optional[ConversationStore] = None


def get_conversation_store() -> ConversationStore:
    """Get the conversation store singleton."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
    return _conversation_store
