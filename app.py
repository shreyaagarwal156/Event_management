from flask import Flask, jsonify, request, send_file, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import jwt
import datetime
from functools import wraps
import re
import pymysql
from sqlalchemy import func

app = Flask(__name__)

USER = 'root'
PASSWORD = 'Root%40123'
HOSTNAME = '127.0.0.1'
PORT = '3306'
DATABASE = 'event_system'

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{USER}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}"
app.config['SECRET_KEY'] = 'a-very-secret-key-that-is-long-and-random'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')

class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='General')
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    venue = db.relationship('Venue')
    organizer = db.relationship('User')

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'event_id', name='_user_event_uc'),)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['id'])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin access required!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered!'}), 409

    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(
        name=data['name'], 
        email=data['email'], 
        password=hashed_password, 
        role='student'
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'New user created! Please login.'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not bcrypt.check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Login failed! Check credentials.'}), 401
    
    token = jwt.encode({
        'id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role
        }
    }), 200

@app.route('/api/events', methods=['GET'])
@token_required
def get_events(current_user):
    events = Event.query.order_by(Event.start_time.desc()).all()
    output = []
    for event in events:
        output.append({
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'start_time': event.start_time.isoformat(),
            'end_time': event.end_time.isoformat(),
            'category': event.category,
            'venue': event.venue.name,
            'organizer': event.organizer.name
        })
    return jsonify({'events': output})

@app.route('/api/events', methods=['POST'])
@token_required
@admin_required
def create_event(current_user):
    data = request.get_json()
    
    venue = Venue.query.filter_by(name=data['venue_name']).first()
    if not venue:
        venue = Venue(name=data['venue_name'], capacity=data.get('venue_capacity', 100))
        db.session.add(venue)
        db.session.commit()
        
    new_event = Event(
        title=data['title'],
        description=data['description'],
        start_time=datetime.datetime.fromisoformat(data['start_time']),
        end_time=datetime.datetime.fromisoformat(data['end_time']),
        category=data['category'],
        venue_id=venue.id,
        organizer_id=current_user.id
    )
    db.session.add(new_event)
    db.session.commit()
    return jsonify({'message': 'Event created successfully!'}), 201

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_event(current_user, event_id):
    event = Event.query.get(event_id)
    if not event:
        return jsonify({'message': 'Event not found!'}), 404
    
    Registration.query.filter_by(event_id=event_id).delete()
    Feedback.query.filter_by(event_id=event_id).delete()
    
    db.session.delete(event)
    db.session.commit()
    return jsonify({'message': 'Event deleted successfully!'}), 200

@app.route('/api/registrations', methods=['GET'])
@token_required
def get_my_registrations(current_user):
    regs = Registration.query.filter_by(user_id=current_user.id).all()
    event_ids = [r.event_id for r in regs]
    my_events = Event.query.filter(Event.id.in_(event_ids)).all()
    
    output = []
    for event in my_events:
         output.append({
            'id': event.id,
            'title': event.title,
            'start_time': event.start_time.isoformat(),
            'category': event.category,
            'venue': event.venue.name
        })
    return jsonify({'registrations': output})

@app.route('/api/register-event', methods=['POST'])
@token_required
def register_for_event(current_user):
    data = request.get_json()
    event_id = data['event_id']
    
    if current_user.role == 'admin':
        return jsonify({'message': 'Admins cannot register for events.'}), 403

    if Registration.query.filter_by(user_id=current_user.id, event_id=event_id).first():
        return jsonify({'message': 'You are already registered for this event!'}), 409
        
    new_reg = Registration(user_id=current_user.id, event_id=event_id)
    db.session.add(new_reg)
    db.session.commit()
    return jsonify({'message': 'Registered successfully!'}), 201

@app.route('/api/feedback', methods=['POST'])
@token_required
def submit_feedback(current_user):
    data = request.get_json()
    
    if current_user.role == 'admin':
        return jsonify({'message': 'Admins cannot submit feedback.'}), 403

    new_feedback = Feedback(
        user_id=current_user.id,
        event_id=data['event_id'],
        rating=data['rating'],
        comment=data['comment']
    )
    db.session.add(new_feedback)
    db.session.commit()
    return jsonify({'message': 'Feedback submitted successfully!'}), 201

@app.route('/api/feedback-analytics/<int:event_id>', methods=['GET'])
@token_required
@admin_required
def get_feedback_analytics(current_user, event_id):
    feedbacks = Feedback.query.filter_by(event_id=event_id).all()
    if not feedbacks:
        return jsonify({'message': 'No feedback for this event yet.'}), 404
        
    total = len(feedbacks)
    sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}
    ratings = []
    
    for f in feedbacks:
        sentiment = simple_sentiment(f.comment)
        sentiments[sentiment] += 1
        ratings.append(f.rating)
        
    sentiments_percent = {
        'positive': (sentiments['positive'] / total) * 100,
        'negative': (sentiments['negative'] / total) * 100,
        'neutral': (sentiments['neutral'] / total) * 100,
    }
    avg_rating = sum(ratings) / total if total > 0 else 0
    
    return jsonify({
        'event_id': event_id,
        'total_feedback': total,
        'average_rating': round(avg_rating, 2),
        'sentiment_analysis': sentiments_percent
    }), 200

@app.route('/api/profile-analytics', methods=['GET'])
@token_required
def get_profile_analytics(current_user):
    total_registrations = Registration.query.filter_by(user_id=current_user.id).count()
    total_feedback = Feedback.query.filter_by(user_id=current_user.id).count()
    
    favorite_category = db.session.query(
        Event.category, func.count(Event.category).label('category_count')
    ).join(
        Registration, Registration.event_id == Event.id
    ).filter(
        Registration.user_id == current_user.id
    ).group_by(
        Event.category
    ).order_by(
        func.count(Event.category).desc()
    ).first()
    
    return jsonify({
        'total_registrations': total_registrations,
        'total_feedback_submitted': total_feedback,
        'favorite_category': favorite_category[0] if favorite_category else 'None'
    })

@app.route('/api/ai-recommendations', methods=['GET'])
@token_required
def get_ai_recommendations(current_user):
    favorite_category_query = db.session.query(
        Event.category
    ).join(
        Registration, Registration.event_id == Event.id
    ).filter(
        Registration.user_id == current_user.id
    ).group_by(
        Event.category
    ).order_by(
        func.count(Event.category).desc()
    ).first()
    
    if not favorite_category_query:
        return jsonify({'recommendations': []})

    fav_category = favorite_category_query[0]

    registered_event_ids = [
        reg.event_id for reg in Registration.query.filter_by(user_id=current_user.id).all()
    ]

    recommendations = Event.query.filter(
        Event.category == fav_category,
        Event.start_time > datetime.datetime.utcnow(),
        ~Event.id.in_(registered_event_ids)
    ).limit(3).all()

    output = []
    for event in recommendations:
        output.append({
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'start_time': event.start_time.isoformat(),
            'category': event.category,
            'venue': event.venue.name
        })

    return jsonify({'recommendations': output})


def simple_sentiment(comment):
    if not comment: return 'neutral'
    comment_lower = comment.lower()
    positive_words = ['good', 'great', 'awesome', 'amazing', 'loved', 'best']
    negative_words = ['bad', 'poor', 'terrible', 'worst', 'awful']
    
    pos_count = sum([1 for word in positive_words if word in comment_lower])
    neg_count = sum([1 for word in negative_words if word in comment_lower])
    
    if pos_count > neg_count: return 'positive'
    if neg_count > pos_count: return 'negative'
    return 'neutral'

@app.route('/')
def home():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template_string(html_content)
    except FileNotFoundError:
        return "Error: index.html not found.", 404

def setup_database():
    try:
        db.create_all()
        
        admin = User.query.filter_by(email='admin@geu.ac.in').first()
        if not admin:
            hashed_pass = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = User(name='Admin', email='admin@geu.ac.in', password=hashed_pass, role='admin')
            db.session.add(admin)
            print("Default admin user (admin@geu.ac.in / admin123) created.")

        venue = Venue.query.filter_by(name='GEU Auditorium').first()
        if not venue:
            venue = Venue(name='GEU Auditorium', capacity=1000)
            db.session.add(venue)
            print("Default 'GEU Auditorium' venue created.")

        db.session.commit()
        print("Database tables checked and initial data added.")
    except Exception as e:
        print(f"Database setup error: {e}")
        print("--- !!! ---")
        print("ERROR: Is your MySQL server (Workbench) running?")
        print("ERROR: Did you create the 'event_system' database (Step 1)?")
        print("ERROR: Is your password 'Root%40123' correct?")
        print("--- !!! ---")
        db.session.rollback()

if __name__ == '__main__':
    with app.app_context():
        setup_database()
    
    app.run(debug=True)
