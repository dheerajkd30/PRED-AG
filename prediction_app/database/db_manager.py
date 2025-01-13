from typing import List, Optional
import json
from datetime import datetime
from .models import Session, Question, User, user_questions
from sqlalchemy.sql import func

class DatabaseManager:
    def __init__(self):
        self.session = Session()

    def create_user(self, username: str, interests: List[str]) -> int:
        """Create a new user and return their ID"""
        user = User(
            username=username,
            interests=json.dumps(interests)
        )
        self.session.add(user)
        self.session.commit()
        return user.id

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username"""
        user = self.session.query(User).filter(User.username == username).first()
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'interests': json.loads(user.interests),
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        return None

    def get_unused_question(self, interest: str, user_id: int) -> Optional[dict]:
        """Get a random question that hasn't been shown to this user"""
        # Get questions for the interest that haven't been viewed by this user
        subquery = self.session.query(user_questions.c.question_id)\
            .filter(user_questions.c.user_id == user_id)\
            .subquery()
            
        question = self.session.query(Question)\
            .filter(Question.interest == interest)\
            .filter(~Question.id.in_(subquery))\
            .order_by(func.random())\
            .first()
            
        if question:
            return {
                'id': question.id,
                'question': question.question_text,
                'interest': question.interest,
                'source_articles': json.loads(question.source_articles),
                'created_at': question.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        return None

    def mark_question_as_viewed(self, question_id: int, user_id: int) -> None:
        """Mark that a user has viewed a question"""
        self.session.execute(
            user_questions.insert().values(
                user_id=user_id,
                question_id=question_id,
                viewed_at=datetime.utcnow()
            )
        )
        self.session.commit()

    def get_user_question_history(self, user_id: int, interest: Optional[str] = None) -> List[dict]:
        """Get questions viewed by a specific user"""
        query = self.session.query(Question, user_questions.c.viewed_at)\
            .join(user_questions)\
            .filter(user_questions.c.user_id == user_id)
            
        if interest:
            query = query.filter(Question.interest == interest)
            
        results = query.order_by(user_questions.c.viewed_at.desc()).all()
        
        return [{
            'id': q.Question.id,
            'question': q.Question.question_text,
            'interest': q.Question.interest,
            'source_articles': json.loads(q.Question.source_articles),
            'viewed_at': q.viewed_at.strftime('%Y-%m-%d %H:%M:%S')
        } for q in results] 

    def save_question(self, question_text: str, interest: str, source_articles: List[str]) -> int:
        """Save a generated question to the database and return its ID"""
        question = Question(
            question_text=question_text,
            interest=interest,
            source_articles=json.dumps(source_articles)
        )
        self.session.add(question)
        self.session.commit()
        return question.id 