from typing import List, Optional, Dict
import json
from datetime import datetime, timedelta
from .models import Session, Question, User, user_questions
from sqlalchemy.sql import func
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

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
        """Get user by username with sanitized input"""
        try:
            # Use parameterized query
            user = self.session.query(User)\
                .filter(User.username == username)\
                .first()
            
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'interests': json.loads(user.interests),
                    'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            return None
        except SQLAlchemyError as e:
            print(f"Database error: {str(e)}")
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
        """Mark question as viewed with input validation"""
        try:
            # Validate inputs
            if not isinstance(question_id, int) or not isinstance(user_id, int):
                raise ValueError("Invalid input types")
            
            # Use SQLAlchemy's built-in parameter binding
            self.session.execute(
                user_questions.insert().values(
                    user_id=user_id,
                    question_id=question_id,
                    viewed_at=datetime.utcnow()
                )
            )
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Database error: {str(e)}")

    def get_user_question_history(self, user_id: int, interest: Optional[str] = None) -> List[dict]:
        """Get questions viewed by a specific user"""
        try:
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
                'viewed_at': q.viewed_at.strftime('%Y-%m-%d %H:%M:%S'),
                'created_at': q.Question.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for q in results]
        except Exception as e:
            return []

    def save_question(self, question_text: str, interest: str, source_articles: List[str]) -> int:
        """Save a question with resolution date"""
        # Extract resolution date from question text (implement this based on your needs)
        resolution_date = self._extract_resolution_date(question_text)
        
        question = Question(
            question_text=question_text,
            interest=interest,
            source_articles=json.dumps(source_articles),
            resolution_date=resolution_date,
            status='pending'
        )
        self.session.add(question)
        self.session.commit()
        return question.id

    def _extract_resolution_date(self, question: str) -> datetime:
        """Extract resolution date from question text"""
        # This is a simple implementation - enhance based on your needs
        now = datetime.utcnow()
        
        # Check for specific time markers
        if 'tomorrow' in question.lower():
            return now + timedelta(days=1)
        elif 'this week' in question.lower():
            return now + timedelta(days=7)
        elif 'weekend' in question.lower():
            # Calculate next Sunday
            days_until_sunday = (6 - now.weekday()) % 7
            return now + timedelta(days=days_until_sunday)
            
        # Default to 7 days if no specific time found
        return now + timedelta(days=7)

    def get_pending_resolutions(self) -> List[dict]:
        """Get questions that need resolution (not yet resolved)"""
        now = datetime.utcnow()
        questions = self.session.query(Question)\
            .filter(Question.resolved_at.is_(None))\
            .all()
            
        return [{
            'id': q.id,
            'question': q.question_text,
            'interest': q.interest,
            'created_at': q.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'source_articles': json.loads(q.source_articles),
            'source_links': json.loads(q.source_links)
        } for q in questions]

    def resolve_question(self, question_id: int, result: bool, note: str = None) -> None:
        """Resolve question with input validation"""
        try:
            if not isinstance(question_id, int):
                raise ValueError("Invalid question_id type")
            if not isinstance(result, bool):
                raise ValueError("Invalid result type")
            if note is not None:
                note = str(note)[:500]  # Limit note length
            
            question = self.session.query(Question).get(question_id)
            if question:
                question.resolved_at = datetime.utcnow()
                question.outcome = result
                question.resolution_note = note
                self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Database error: {str(e)}")

    def update_user_interests(self, user_id: int, interests: List[str]) -> None:
        """Update user interests with input validation"""
        try:
            # Validate inputs
            if not isinstance(user_id, int):
                raise ValueError("Invalid user_id type")
            if not isinstance(interests, list):
                raise ValueError("Invalid interests type")
            
            # Sanitize interests
            interests = [str(i).lower() for i in interests]
            
            user = self.session.query(User).filter(User.id == user_id).first()
            if user:
                user.interests = json.dumps(interests)
                self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Database error: {str(e)}")

    def get_multiple_unused_questions(self, interest: str, user_id: int, count: int = 5) -> List[dict]:
        """Get multiple random questions with sanitized inputs"""
        try:
            # Validate inputs
            if not isinstance(user_id, int) or not isinstance(count, int):
                raise ValueError("Invalid input types")
            
            interest = str(interest).lower()  # Sanitize interest
            
            subquery = self.session.query(user_questions.c.question_id)\
                .filter(user_questions.c.user_id == user_id)\
                .subquery()
                
            questions = self.session.query(Question)\
                .filter(Question.interest == interest)\
                .filter(~Question.id.in_(subquery))\
                .order_by(func.random())\
                .limit(count)\
                .all()
                
            return [{
                'id': q.id,
                'question': q.question_text,
                'interest': q.interest,
                'source_articles': json.loads(q.source_articles),
                'created_at': q.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for q in questions]
        except SQLAlchemyError as e:
            print(f"Database error: {str(e)}")
            return []

    def create_question(self, question_text: str, interest: str, 
                       source_articles: List[str], source_links: List[str]) -> int:
        """Create a new question and return its ID"""
        question = Question(
            question_text=question_text,
            interest=interest,
            source_articles=json.dumps(source_articles),
            source_links=json.dumps(source_links)
        )
        self.session.add(question)
        self.session.commit()
        return question.id

    def get_questions(self, interest: str = None) -> List[Dict]:
        """Get all questions, optionally filtered by interest"""
        query = self.session.query(Question)
        if interest:
            query = query.filter(Question.interest == interest)
            
        questions = query.all()
        return [{
            'id': q.id,
            'question': q.question_text,
            'interest': q.interest,
            'source_articles': json.loads(q.source_articles),
            'source_links': json.loads(q.source_links),
            'created_at': q.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'resolved_at': q.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if q.resolved_at else None,
            'outcome': q.outcome,
            'resolution_note': q.resolution_note
        } for q in questions]