from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
import bcrypt
import jwt
import datetime
from functools import wraps
import re

app = Flask(__name__)

# --- Configuration for Database and Secret Key ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://admin:password123@postgres:5432/escoba_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super_secret_key')

db = SQLAlchemy(app)

# --- DataBase Model for User ---
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email
        }

with app.app_context():
    db.create_all()

# --- FUNCTIONS HELPER ---

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if "Bearer " in auth_header:
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

def validate_password_complexity(password):
    if len(password) < 8 or len(password) > 20:
        return False, "Password must be between 8 and 20 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[ !@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        return False, "Password must contain at least one special character."
    return True, None

# --- ENDPOINTS ---

@app.route('/auth/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "auth-service"}), 200

# New endpoint to get all users (for admin purposes)
@app.route('/auth/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users]), 200

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password') or not data.get('email'):
        return jsonify({"error": "Missing username, email or password"}), 400
    
    is_valid, error_msg = validate_password_complexity(data['password'])
    if not is_valid:
        return jsonify({"error": error_msg}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists"}), 409

    new_user = User(username=data['username'], email=data['email'])
    new_user.set_password(data['password'])
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Missing credentials"}), 400

    user = User.query.filter_by(username=data['username']).first()

    if user and user.check_password(data['password']):
        token_payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user_id": user.id
        }), 200
    else:
        return jsonify({"error": "Invalid username or password"}), 401

@app.route('/auth/validate', methods=['POST'])
def validate_token():
    token = request.json.get('token')
    if not token: return jsonify({"valid": False, "error": "Missing token"}), 400
    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({"valid": True, "user_id": decoded['user_id'], "username": decoded['username']}), 200
    except Exception:
        return jsonify({"valid": False}), 401

@app.route('/auth/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify(current_user.to_dict()), 200

@app.route('/auth/update', methods=['PUT'])
@token_required
def update_user(current_user):
    data = request.get_json()
    if 'email' in data and data['email']:
        existing = User.query.filter_by(email=data['email']).first()
        if existing and existing.id != current_user.id:
            return jsonify({"error": "Email already in use"}), 409
        current_user.email = data['email']
    
    if 'password' in data and data['password']:
        is_valid, error_msg = validate_password_complexity(data['password'])
        if not is_valid: return jsonify({"error": error_msg}), 400
        current_user.set_password(data['password'])
        
    try:
        db.session.commit()
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)