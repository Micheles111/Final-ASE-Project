from flask import Flask, jsonify, request
import redis
import json
import uuid
import random
import os
import itertools
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import datetime

app = Flask(__name__)

redis_host = os.environ.get('REDIS_HOST', 'redis')
r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

HISTORY_SERVICE_URL = "https://history-service:5000/history/matches"
PLAYER_SERVICE_URL = "https://player-service:5000/players"

MATCHMAKING_QUEUE_KEY = "matchmaking_queue"

# --- UTILS CARTS ---
def get_initial_deck():
    return list(range(1, 41))

def get_card_value(card_id):
    val = (card_id - 1) % 10 + 1
    return val

def is_oros(card_id):
    return 1 <= card_id <= 10

def is_settebello(card_id):
    return card_id == 7

def find_capture_combination(played_card_id, table_ids):
    played_val = get_card_value(played_card_id)
    target = 15 - played_val
    if target <= 0: return []
    
    table_map = {cid: get_card_value(cid) for cid in table_ids}
    valid_combinations = []
    
    for L in range(1, len(table_ids) + 1):
        for subset in itertools.combinations(table_ids, L):
            current_sum = sum(table_map[c] for c in subset)
            if current_sum == target:
                valid_combinations.append(list(subset))
    
    if not valid_combinations: return []
    valid_combinations.sort(key=len, reverse=True)
    return valid_combinations[0]

def calculate_scores(state):
    scores = {}
    details = {}
    if 'players' not in state: return {}, {}

    for player, data in state['players'].items():
        points = 0
        captured = data['captured']
        score_log = []

        escobas = data['score_events'].count("ESCOBA")
        points += escobas
        if escobas > 0: score_log.append(f"{escobas} Escoba(s)")

        if len(captured) > 20:
            points += 1
            score_log.append("Most Cards")
        
        oros_count = sum(1 for c in captured if is_oros(c))
        if oros_count > 5:
            points += 1
            score_log.append("Most Coins")

        if any(is_settebello(c) for c in captured):
            points += 1
            score_log.append("Settebello")
            
        scores[player] = points
        details[player] = score_log
    return scores, details

def finalize_match(state, surrender_winner=None):
    winner = None
    final_scores = {}
    score_details = {}

    if surrender_winner:
        winner = surrender_winner
        p1, p2 = list(state['players'].keys())
        final_scores = {p1: 0, p2: 0}
        score_details = {winner: ["Opponent Surrendered"]}
    else:
        last_capturer = state.get('last_capture_by')
        if last_capturer and state['table']:
            state['players'][last_capturer]['captured'].extend(state['table'])
            state['table'] = []

        final_scores, score_details = calculate_scores(state)
        p1, p2 = list(final_scores.keys())
        if final_scores[p1] > final_scores[p2]: winner = p1
        elif final_scores[p2] > final_scores[p1]: winner = p2
        else: winner = "Draw"

    try:
        players_list = list(state['players'].keys())
        history_payload = {
            "match_id": state['match_id'],
            "player1": players_list[0],
            "player2": players_list[1],
            "winner": winner if winner != "Draw" else None,
            "score": final_scores,
            "log": score_details
        }
        requests.post(HISTORY_SERVICE_URL, json=history_payload, timeout=2, verify='/app/certs/cert.pem')
    except Exception as e:
        print(f"Error contacting History Service: {e}")

    for p in state['players'].keys():
        if p == "CPU" or p == "Guest": continue
        try:
            is_winner = (p == winner)
            points = final_scores.get(p, 0)
            stats_payload = {"won": is_winner, "score_delta": points}
            requests.put(f"{PLAYER_SERVICE_URL}/{p}/stats", json=stats_payload, timeout=2, verify='/app/certs/cert.pem')
        except Exception as e:
            print(f"Error contacting Player Service for {p}: {e}")

    return {
        "status": "finished",
        "winner": winner,
        "final_scores": final_scores,
        "details": score_details
    }

def execute_cpu_turn(state):
    cpu_hand = state['players']['CPU']['hand']
    table = state['table']
    move_card = None
    captured = []
    
    for card in cpu_hand:
        combo = find_capture_combination(card, table)
        if combo:
            move_card = card
            captured = combo
            break
    
    if not move_card:
        cpu_hand.sort(key=get_card_value)
        move_card = cpu_hand[0]
        captured = []

    state['players']['CPU']['hand'].remove(move_card)
    
    if captured:
        for c in captured: state['table'].remove(c)
        state['players']['CPU']['captured'].extend(captured + [move_card])
        state['last_capture_by'] = "CPU"
        if not state['table']:
            state['players']['CPU']['score_events'].append("ESCOBA")
    else:
        state['table'].append(move_card)
        
    return state

def handle_turn_change(state):
    players_list = list(state['players'].keys())
    current_turn = state['turn']
    idx = players_list.index(current_turn)
    next_player = players_list[(idx + 1) % 2]
    
    p1 = players_list[0]
    p2 = players_list[1]
    
    p1_empty = len(state['players'][p1]['hand']) == 0
    p2_empty = len(state['players'][p2]['hand']) == 0
    
    message = "Turn changed"
    finished = False
    
    if p1_empty and p2_empty:
        if len(state['deck']) > 0:
            deal_count = 3
            if len(state['deck']) < 6: deal_count = len(state['deck']) // 2
            
            for _ in range(deal_count):
                state['players'][p1]['hand'].append(state['deck'].pop())
                state['players'][p2]['hand'].append(state['deck'].pop())
            message = "New hand dealt"
            state['turn'] = next_player
        else:
            final_result = finalize_match(state)
            state['status'] = 'finished'
            state['result'] = final_result
            message = "Match finished"
            state['turn'] = None
            finished = True
    else:
        state['turn'] = next_player
        state['turn_start_time'] = datetime.datetime.utcnow().isoformat()
        
    return state, message, finished

def start_real_match(player1, player2):
    match_id = str(uuid.uuid4())
    deck = get_initial_deck()
    random.shuffle(deck)
    p1_hand = [deck.pop() for _ in range(3)]
    p2_hand = [deck.pop() for _ in range(3)]
    table = [deck.pop() for _ in range(4)]

    match_state = {
        "match_id": match_id,
        "players": {
            player1: {"hand": p1_hand, "captured": [], "score_events": []},
            player2: {"hand": p2_hand, "captured": [], "score_events": []}
        },
        "table": table,
        "deck": deck,
        "turn": player1,
        "status": "active",
        "last_capture_by": None,
        "turn_start_time": datetime.datetime.utcnow().isoformat()
    }
    r.setex(f"match:{match_id}", 7200, json.dumps(match_state))
    return match_id

# --- ENDPOINTS ---

@app.route('/matches/health', methods=['GET'])
def health():
    try:
        r.ping()
        db_status = "connected"
    except redis.ConnectionError:
        db_status = "disconnected"
    return jsonify({"status": "healthy", "service": "match-service", "redis": db_status}), 200

@app.route('/matches/pending/<username>', methods=['GET'])
def get_pending_matches(username):
    active_matches = []
    invites_received = []
    invites_sent = []
    
    for key in r.scan_iter("match:*"):
        try:
            state_json = r.get(key)
            if not state_json: continue
            state = json.loads(state_json)
            status = state.get('status')
            
            if status == 'active' and username in state.get('players', {}):
                players = list(state['players'].keys())
                opponent = players[1] if players[0] == username else players[0]
                current_scores, _ = calculate_scores(state)
                active_matches.append({
                    "match_id": state['match_id'],
                    "opponent": opponent,
                    "turn": state['turn'],
                    "scores": current_scores
                })
            elif status == 'pending' and state.get('player2') == username:
                invites_received.append({
                    "match_id": state['match_id'],
                    "challenger": state['player1']
                })
            elif status == 'pending' and state.get('player1') == username:
                invites_sent.append({
                    "match_id": state['match_id'],
                    "opponent": state['player2']
                })
        except Exception as e:
            print(f"Error reading match {key}: {e}")
            
    return jsonify({
        "active": active_matches,
        "invites_received": invites_received,
        "invites_sent": invites_sent
    }), 200

@app.route('/invites', methods=['POST'])
def create_invite():
    data = request.get_json()
    player1 = data.get('player1')
    player2 = data.get('player2')
    if not player1 or not player2: return jsonify({"error": "Two players required"}), 400
    match_id = str(uuid.uuid4())
    invite_state = {"match_id": match_id, "player1": player1, "player2": player2, "status": "pending"}
    r.setex(f"match:{match_id}", 86400, json.dumps(invite_state))
    return jsonify({"match_id": match_id, "message": "Invite sent"}), 201

@app.route('/invites/<match_id>/accept', methods=['POST'])
def accept_invite(match_id):
    data = request.get_json()
    player_accepting = data.get('player')
    state_json = r.get(f"match:{match_id}")
    if not state_json: return jsonify({"error": "Invite not found"}), 404
    state = json.loads(state_json)
    if state['status'] != 'pending': return jsonify({"error": "Match already active"}), 400
    if state['player2'] != player_accepting: return jsonify({"error": "Not authorized"}), 403

    r.delete(f"match:{match_id}")
    new_match_id = start_real_match(state['player1'], state['player2'])
    
    deck = get_initial_deck()
    random.shuffle(deck)
    p1_hand = [deck.pop() for _ in range(3)]
    p2_hand = [deck.pop() for _ in range(3)]
    table = [deck.pop() for _ in range(4)]

    match_state = {
        "match_id": match_id,
        "players": {
            state['player1']: {"hand": p1_hand, "captured": [], "score_events": []},
            state['player2']: {"hand": p2_hand, "captured": [], "score_events": []}
        },
        "table": table,
        "deck": deck,
        "turn": state['player1'],
        "status": "active",
        "last_capture_by": None
    }
    r.setex(f"match:{match_id}", 7200, json.dumps(match_state))
    
    return jsonify({"match_id": match_id, "message": "Match accepted"}), 200

@app.route('/invites/<match_id>/reject', methods=['POST'])
def reject_invite(match_id):
    data = request.get_json()
    player_rejecting = data.get('player')
    state_json = r.get(f"match:{match_id}")
    if not state_json: return jsonify({"error": "Invite not found"}), 404
    state = json.loads(state_json)
    if state['player2'] != player_rejecting and state['player1'] != player_rejecting:
        return jsonify({"error": "Not authorized"}), 403
    r.delete(f"match:{match_id}")
    return jsonify({"message": "Invite rejected"}), 200

@app.route('/matchmaking/join', methods=['POST'])
def join_matchmaking():
    data = request.get_json()
    player = data.get('player')
    opponent = r.lpop(MATCHMAKING_QUEUE_KEY)
    
    if opponent and opponent != player:
        match_id = start_real_match(opponent, player)
        r.setex(f"matchmaking:user:{opponent}", 60, match_id)
        r.setex(f"matchmaking:user:{player}", 60, match_id)
        return jsonify({"status": "matched", "match_id": match_id, "opponent": opponent}), 200
    else:
        r.lrem(MATCHMAKING_QUEUE_KEY, 0, player)
        r.rpush(MATCHMAKING_QUEUE_KEY, player)
        r.delete(f"matchmaking:user:{player}")
        return jsonify({"status": "waiting"}), 200

@app.route('/matchmaking/status/<username>', methods=['GET'])
def matchmaking_status(username):
    match_id = r.get(f"matchmaking:user:{username}")
    if match_id: return jsonify({"status": "matched", "match_id": match_id}), 200
    queue = r.lrange(MATCHMAKING_QUEUE_KEY, 0, -1)
    if username in queue: return jsonify({"status": "waiting"}), 200
    return jsonify({"status": "none"}), 200

@app.route('/matchmaking/leave', methods=['POST'])
def leave_matchmaking():
    data = request.get_json()
    player = data.get('player')
    r.lrem(MATCHMAKING_QUEUE_KEY, 0, player)
    return jsonify({"message": "Left queue"}), 200

@app.route('/matches', methods=['POST'])
def create_match():
    data = request.get_json()
    player1 = data.get('player1')
    player2 = data.get('player2')
    match_id = start_real_match(player1, player2)
    return jsonify({"match_id": match_id, "message": "Match created", "turn": player1}), 201

@app.route('/matches/<match_id>', methods=['GET'])
def get_match(match_id):
    state_json = r.get(f"match:{match_id}")
    if not state_json: return jsonify({"error": "Match not found"}), 404
    state = json.loads(state_json)
    if state.get('status') == 'pending': return jsonify(state), 200
    if state['status'] == 'finished': return jsonify(state), 200
    
    requesting_player = request.args.get('player')
    players = state['players']
    
    # IF IT'S GUEST (LOCAL), WE DON'T HIDE ANYTHING
    # The backend sends everything, the frontend decides what to show
    is_local_game = "Guest" in players
    
    if not requesting_player and not is_local_game: return jsonify(state), 200
    if requesting_player and requesting_player not in players and not is_local_game:
        return jsonify({"error": "Player not in this match"}), 403

    sanitized_state = state.copy()
    sanitized_state['cards_remaining'] = len(state['deck'])
    current_scores, _ = calculate_scores(state)
    sanitized_state['current_scores'] = current_scores

    if not is_local_game:
        for p_name in players:
            if p_name != requesting_player:
                sanitized_state['players'][p_name]['hand'] = ["hidden"] * len(players[p_name]['hand'])
                sanitized_state.pop('deck', None)

    return jsonify(sanitized_state), 200

@app.route('/matches/<match_id>/play', methods=['POST'])
def play_card(match_id):
    data = request.get_json()
    player = data.get('player')
    card_id = data.get('card_id')
    state_json = r.get(f"match:{match_id}")
    if not state_json: return jsonify({"error": "Match not found"}), 404
    state = json.loads(state_json)
    if state['status'] != 'active': return jsonify({"error": "Match finished/pending"}), 400
    if state['turn'] != player: return jsonify({"error": "Not your turn"}), 400
    if card_id not in state['players'][player]['hand']: return jsonify({"error": "Card not in hand"}), 400

    captured_cards = find_capture_combination(card_id, state['table'])
    escoba = False
    state['players'][player]['hand'].remove(card_id)
    if captured_cards:
        for c in captured_cards: state['table'].remove(c)
        state['players'][player]['captured'].extend(captured_cards + [card_id])
        state['last_capture_by'] = player
        if not state['table']:
            escoba = True
            state['players'][player]['score_events'].append("ESCOBA")
    else:
        state['table'].append(card_id)

    state, message, finished = handle_turn_change(state)
    if not finished and state['turn'] == "CPU":
        state = execute_cpu_turn(state)
        state, cpu_msg, finished = handle_turn_change(state)
        message = "CPU played. Your turn."

    r.setex(f"match:{match_id}", 7200, json.dumps(state))
    response = {
        "message": message, 
        "captured": captured_cards,
        "escoba": escoba,
        "state_snapshot": {"table": state['table'], "your_hand": state['players'][player]['hand']}
    }
    if state['status'] == 'finished':
        response['final_result'] = state['result']
    return jsonify(response), 200

@app.route('/matches/<match_id>/surrender', methods=['POST'])
def surrender_match(match_id):
    data = request.get_json()
    player_surrendering = data.get('player')
    state_json = r.get(f"match:{match_id}")
    if not state_json: return jsonify({"error": "Match not found"}), 404
    state = json.loads(state_json)
    if state['status'] != 'active': return jsonify({"error": "Match finished"}), 400
    players = list(state['players'].keys())
    winner = players[1] if players[0] == player_surrendering else players[0]
    final_result = finalize_match(state, surrender_winner=winner)
    state['status'] = 'finished'
    state['result'] = final_result
    r.setex(f"match:{match_id}", 7200, json.dumps(state))
    return jsonify({"message": "Match surrendered", "winner": winner}), 200

# services/match-service/app.py
@app.route('/matches/<match_id>/react', methods=['POST'])
def post_reaction(match_id):
    data = request.get_json()
    player = data.get('player')
    reaction = data.get('reaction')
    
    state_json = r.get(f"match:{match_id}")
    if not state_json: return jsonify({"error": "Match not found"}), 404
    state = json.loads(state_json)
    
    if state['status'] != 'active': return jsonify({"error": "Match finished/pending"}), 400
    if player not in state['players']: return jsonify({"error": "Player not in this match"}), 403
    
    # Store the reaction in the match state
    state['last_reaction'] = {
        "player": player,
        "content": reaction,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    r.setex(f"match:{match_id}", 7200, json.dumps(state))
    
    return jsonify({"message": "Reaction posted"}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)