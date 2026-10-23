"""Shared authenticated turn orchestration and atomic message persistence."""
from datetime import datetime
import json
import logging

from fastapi import HTTPException
from openai import APITimeoutError, APIConnectionError

from app.auth import get_current_user
from app.conversations import owned_conversation
from app.models import Message


def run_turn(request, credentials, db, mode='rag'):
    from app.knowledge import answer_question, knowledge_lock
    with knowledge_lock():
        db.expire_all()
        user = get_current_user(credentials, db)
        initial_role = user.role
        conversation = owned_conversation(db, request.conversation_id, user)
        previous = db.query(Message).filter_by(conversation_id=conversation.id).order_by(
            Message.created_time.desc(), Message.id.desc()).limit(6).all()
        history = '\n'.join(f'{m.role}: {m.content}' for m in reversed(previous)
                            if mode == 'rag' or m.role == 'user')
        try:
            if mode == 'agent':
                from app.agent_service import answer_agent
                result = answer_agent(request.question, conversation.knowledge_base, user.role, history)
            else:
                result = answer_question(request.question, conversation.knowledge_base, user.role, history)
        except HTTPException:
            raise
        except APITimeoutError:
            raise HTTPException(504, '回答生成超时，请稍后重试；本次问答未保存')
        except APIConnectionError:
            raise HTTPException(503, '暂时无法连接回答模型，请检查网络或稍后重试；本次问答未保存')
        except Exception:
            logging.exception('Chat request failed (%s)', mode)
            raise HTTPException(503, '问答服务暂时不可用，请稍后重试')
        db.rollback()
        refreshed = get_current_user(credentials, db)
        if refreshed.role != initial_role:
            raise HTTPException(409, '权限已变化，请重新提问')
        conversation = owned_conversation(db, request.conversation_id, refreshed)
        metadata = None
        if mode == 'agent':
            metadata = json.dumps({key: result[key] for key in
                ('tool_trace', 'stop_reason', 'timings', 'retrieval_count', 'model_call_count')}, ensure_ascii=False)
        db.add_all([Message(conversation_id=conversation.id, role='user', content=request.question),
                    Message(conversation_id=conversation.id, role='assistant', content=result['answer'],
                            sources=json.dumps(result['sources'], ensure_ascii=False), agent_metadata=metadata)])
        conversation.updated_time = datetime.utcnow()
        db.commit()
        return {'conversation_id': conversation.id, 'question': request.question, **result}
