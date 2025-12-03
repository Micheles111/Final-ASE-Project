from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json

app = Flask(__name__)

# Configuration database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://admin:password123@postgres:5432/escoba_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- HISTORICAL MODEL ---
class MatchRecord(db.Model):
    __tablename__ = 'match_history'
    
    id = db.Column(db.String(36), primary_key=True)
    date_played = db.Column(db.DateTime, default=datetime.utcnow)
    player1 = db.Column(db.String(50), nullable=False)
    player2 = db.Column(db.String(50), nullable=False)
    winner = db.Column(db.String(50), nullable=True)
    final_score = db.Column(db.String(200)) # JSON string
    match_log = db.Column(db.Text) # JSON string

    def to_dict(self):
        """Versione sintetica per la lista"""
        # Secure score parsing
        score_data = {}
        try:
            score_data = json.loads(self.final_score) if self.final_score else {}
        except:
            score_data = str(self.final_score)

        return {
            "match_id": self.id,
            "date": self.date_played.isoformat(),
            "players": [self.player1, self.player2],
            "winner": self.winner,
            "score": score_data
        }

    def to_full_dict(self):
        """Versione completa per il dettaglio"""
        base = self.to_dict()
        try:
            base["log"] = json.loads(self.match_log) if self.match_log else {}
        except:
            base["log"] = {}
        return base

with app.app_context():
    db.create_all()

# --- ENDPOINTS ---

@app.route('/history/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "history-service"}), 200

@app.route('/history/matches', methods=['POST'])
def save_match():
    data = request.get_json()
    
    if not data or 'match_id' not in data:
        return jsonify({"error": "Invalid data"}), 400
        
    if MatchRecord.query.get(data['match_id']):
        return jsonify({"message": "Match already saved"}), 200

    new_record = MatchRecord(
        id=data['match_id'],
        player1=data['player1'],
        player2=data['player2'],
        winner=data.get('winner'),
        final_score=json.dumps(data.get('score', {})),
        match_log=json.dumps(data.get('log', []))
    )
    
    try:
        db.session.add(new_record)
        db.session.commit()
        return jsonify({"message": "Match archived successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/history/<username>', methods=['GET'])
def get_user_history(username):
    matches = MatchRecord.query.filter(
        (MatchRecord.player1 == username) | (MatchRecord.player2 == username)
    ).order_by(MatchRecord.date_played.desc()).all()
    
    return jsonify([m.to_dict() for m in matches]), 200

# --- New Endpoint: Match Details ---
@app.route('/history/match/<match_id>', methods=['GET'])
def get_match_details(match_id):
    match = MatchRecord.query.get(match_id)
    if not match:
        return jsonify({"error": "Match not found"}), 404
    
    return jsonify(match.to_full_dict()), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)