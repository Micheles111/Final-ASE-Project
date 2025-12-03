from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuration DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://admin:password123@postgres:5432/escoba_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class Player(db.Model):
    __tablename__ = 'players'
    username = db.Column(db.String(50), primary_key=True)
    matches_played = db.Column(db.Integer, default=0)
    matches_won = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "username": self.username,
            "matches_played": self.matches_played,
            "matches_won": self.matches_won,
            "total_score": self.total_score,
            "win_rate": (self.matches_won / self.matches_played * 100) if self.matches_played > 0 else 0,
            "online": self.is_online()
        }
        
    def is_online(self):
        if not self.last_seen: return False
        return (datetime.utcnow() - self.last_seen) < timedelta(minutes=2)

class Friendship(db.Model):
    __tablename__ = 'friendships'
    id = db.Column(db.Integer, primary_key=True)
    requester = db.Column(db.String(50), db.ForeignKey('players.username'), nullable=False)
    receiver = db.Column(db.String(50), db.ForeignKey('players.username'), nullable=False)
    status = db.Column(db.String(20), default='pending')

with app.app_context():
    db.create_all()

# --- ENDPOINTS ---

@app.route('/players/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "player-service"}), 200

@app.route('/players/<username>/heartbeat', methods=['POST'])
def heartbeat(username):
    player = Player.query.get(username)
    if player:
        player.last_seen = datetime.utcnow()
        db.session.commit()
    return jsonify({"status": "ok"}), 200

@app.route('/players/list/all', methods=['GET'])
def get_all_players():
    players = Player.query.all()
    return jsonify([p.to_dict() for p in players]), 200

@app.route('/players/<username>', methods=['POST'])
def create_profile(username):
    if Player.query.get(username):
        return jsonify({"message": "Profile already exists"}), 200
    
    new_player = Player(username=username)
    db.session.add(new_player)
    db.session.commit()
    return jsonify(new_player.to_dict()), 201

@app.route('/players/<username>', methods=['GET'])
def get_profile(username):
    player = Player.query.get(username)
    if not player:
        return jsonify({"error": "Player not found"}), 404
    return jsonify(player.to_dict()), 200

@app.route('/players/<username>/stats', methods=['PUT'])
def update_stats(username):
    player = Player.query.get(username)
    if not player:
        return jsonify({"error": "Player not found"}), 404
    
    data = request.get_json()
    if data.get('won', False):
        player.matches_won += 1
    player.matches_played += 1
    player.total_score += data.get('score_delta', 0)
    
    db.session.commit()
    return jsonify(player.to_dict()), 200

@app.route('/players/leaderboard/top', methods=['GET'])
def get_leaderboard():
    top_players = Player.query.order_by(
        Player.matches_won.desc(), 
        Player.total_score.desc()
    ).limit(50).all()
    return jsonify([p.to_dict() for p in top_players]), 200

# --- FRIENDS SECTION ---
@app.route('/friends/list/<username>', methods=['GET'])
def get_friends_list(username):
    me = Player.query.get(username)
    if me:
        me.last_seen = datetime.utcnow()
        db.session.commit()

    friends_query = Friendship.query.filter(
        and_(
            or_(Friendship.requester == username, Friendship.receiver == username),
            Friendship.status == 'accepted'
        )
    ).all()
    
    friends_data = []
    for f in friends_query:
        friend_name = f.receiver if f.requester == username else f.requester
        friend_obj = Player.query.get(friend_name)
        if friend_obj:
            friends_data.append({
                "username": friend_obj.username,
                "online": friend_obj.is_online()
            })
        
    pending_query = Friendship.query.filter_by(receiver=username, status='pending').all()
    pending = [f.requester for f in pending_query]
    
    sent_query = Friendship.query.filter_by(requester=username, status='pending').all()
    sent = [f.receiver for f in sent_query]
    
    return jsonify({
        "friends": friends_data,
        "pending_received": pending,
        "pending_sent": sent
    }), 200

@app.route('/friends/request', methods=['POST'])
def send_friend_request():
    data = request.get_json()
    sender = data.get('sender')
    target = data.get('target')
    
    if sender == target: return jsonify({"error": "Cannot add yourself"}), 400
    if not Player.query.get(target): return jsonify({"error": "Player not found"}), 404
    
    # Control: Check if a relationship (pending or accepted) already exists in ANY direction
    existing = Friendship.query.filter(
        or_(
            and_(Friendship.requester == sender, Friendship.receiver == target),
            and_(Friendship.requester == target, Friendship.receiver == sender)
        )
    ).first()
    
    if existing:
        if existing.status == 'accepted':
            return jsonify({"error": "Already friends"}), 409 # Conflict
        return jsonify({"error": "Request already pending"}), 409 # Conflict
        
    new_friendship = Friendship(requester=sender, receiver=target, status='pending')
    db.session.add(new_friendship)
    db.session.commit()
    return jsonify({"message": "Friend request sent"}), 201

@app.route('/friends/response', methods=['POST'])
def respond_friend_request():
    data = request.get_json()
    user = data.get('user')
    requester = data.get('requester')
    action = data.get('action')
    
    friendship = Friendship.query.filter_by(requester=requester, receiver=user, status='pending').first()
    if not friendship: return jsonify({"error": "Request not found"}), 404
        
    if action == 'accept':
        friendship.status = 'accepted'
        db.session.commit()
        return jsonify({"message": "Friend request accepted"}), 200
    elif action == 'reject':
        db.session.delete(friendship)
        db.session.commit()
        return jsonify({"message": "Friend request rejected"}), 200
    return jsonify({"error": "Invalid action"}), 400

@app.route('/friends/remove', methods=['POST'])
def remove_friend():
    data = request.get_json()
    user = data.get('user')
    friend = data.get('friend')
    
    friendship = Friendship.query.filter(
        or_(
            and_(Friendship.requester == user, Friendship.receiver == friend),
            and_(Friendship.requester == friend, Friendship.receiver == user)
        )
    ).first()
    
    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        return jsonify({"message": "Friend removed"}), 200
        
    return jsonify({"error": "Friendship not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)