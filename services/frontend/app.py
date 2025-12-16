from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import logging
import os
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'frontend_secret_key')
ASMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin123!')
debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

API_GATEWAY = "https://api-gateway:5000"

# --- HELPERS ---

def api_request(method, endpoint, data=None, params=None, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    url = f"{API_GATEWAY}{endpoint}"
    
    try:
        response = requests.request(
            method=method, 
            url=url, 
            json=data, 
            params=params, 
            headers=headers, 
            verify=False 
        )
        return response
    except Exception as e:
        print(f"Error connecting to API: {e}")
        return None

def enrich_card_with_image(card):
    suit_map = {
        "Oros": "oro",
        "Copas": "copas",
        "Espadas": "espadas",
        "Bastos": "bastos"
    }
    suit_name = suit_map.get(card['suit'], "oro")
    val = card['number']
    prefix = str(val)
    if val == 8: prefix = "sota"
    elif val == 9: prefix = "caballo"
    elif val == 10: prefix = "rey"
    card['image_file'] = f"{prefix}_{suit_name}.png"
    return card

def send_heartbeat():
    if 'username' in session:
        api_request("POST", f"/players/{session['username']}/heartbeat", token=session.get('token'))

# --- ROTTE BASE & AUTH ---

@app.route('/')
def index():
    if 'token' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


# services/frontend/app.py
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    resp = api_request("POST", "/auth/login", data={"username": username, "password": password})
    
    if resp and resp.status_code == 200:
        data = resp.json()
        session['token'] = data['token']
        session['user_id'] = data['user_id']
        session['username'] = username
        return redirect(url_for('dashboard'))
    else:
        error_msg = "Login failed."
        try:
            error_msg = resp.json().get('error', 'Login failed.')
        except (ValueError, AttributeError) as e:
            logging.error(f"Error processing JSON response:{e}")
            error_msg = "Internal Server Error"
        flash(f"{error_msg} if you dont have an account, ¡LOGIN NOW!")
        return redirect(url_for('index'))

@app.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    auth_resp = api_request("POST", "/auth/register", data={"username": username, "email": email, "password": password})
    
    if auth_resp and auth_resp.status_code == 201:
        player_resp = api_request("POST", f"/players/{username}")
        if player_resp and player_resp.status_code in [200, 201]:
            flash("Registration successful! Please login.")
        else:
            flash("Account created, but failed to initialize player profile.")
    else:
        error_msg = "Registration failed."
        try:
            error_msg = resp.json().get('error', 'Registration failed.')
        except (ValueError, AttributeError) as e:
            logging.error(f"Error processing JSON response:{e}")
            error_msg = "Internal Server Error"
        flash(error_msg)
        
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'token' not in session: return redirect(url_for('index'))
    send_heartbeat()
    
    profile_resp = api_request("GET", f"/players/{session['username']}", token=session['token'])
    profile = profile_resp.json() if profile_resp and profile_resp.status_code == 200 else {}
    
    pending_resp = api_request("GET", f"/matches/pending/{session['username']}", token=session['token'])
    active_matches = []
    invites_received = []
    invites_sent = []
    
    if pending_resp and pending_resp.status_code == 200:
        data = pending_resp.json()
        if isinstance(data, list):
            active_matches = data
        else:
            active_matches = data.get('active', [])
            invites_received = data.get('invites_received', [])
            invites_sent = data.get('invites_sent', [])
    
    return render_template('dashboard.html', 
                           user=session['username'], 
                           profile=profile, 
                           active_matches=active_matches, 
                           invites_received=invites_received, 
                           invites_sent=invites_sent)

# --- INFO & PROFILO ---

@app.route('/info')
def info():
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("GET", "/cards/cards", token=session['token'])
    cards = []
    if resp and resp.status_code == 200:
        raw_cards = resp.json()
        cards = [enrich_card_with_image(c) for c in raw_cards]
    return render_template('info.html', user=session['username'], cards=cards)

@app.route('/profile')
def profile():
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("GET", "/auth/me", token=session['token'])
    user_info = resp.json() if resp and resp.status_code == 200 else {}
    return render_template('profile.html', user=user_info)

@app.route('/profile/update', methods=['POST'])
def update_profile():
    if 'token' not in session: return redirect(url_for('index'))
    email = request.form.get('email')
    password = request.form.get('password')
    data = {}
    if email: data['email'] = email
    if password: data['password'] = password
    if not data: return redirect(url_for('profile'))
    
    resp = api_request("PUT", "/auth/update", data=data, token=session['token'])
    if resp and resp.status_code == 200:
        flash("Profile updated successfully!")
    else:
        error_msg = "Update failed."
        try: 
            error_msg = resp.json().get('error', 'Update failed.')
        except (ValueError, AttributeError) as e:
            logging.error(f"Error processing JSON response:{e}")
            error_msg = "Internal Server Error"
        flash(error_msg)
    return redirect(url_for('profile'))

@app.route('/leaderboard')
def leaderboard():
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("GET", "/players/leaderboard/top", token=session['token'])
    players = resp.json() if resp and resp.status_code == 200 else []
    return render_template('leaderboard.html', user=session['username'], players=players)

# --- FIX HISTORY & MATCH ANALYSIS ---
@app.route('/match_history')
def match_history_page():
    if 'token' not in session: return redirect(url_for('index'))
    
    history_resp = api_request("GET", f"/history/{session['username']}", token=session['token'])
    history = history_resp.json() if history_resp and history_resp.status_code == 200 else []
    
    friends_resp = api_request("GET", f"/friends/list/{session['username']}", token=session['token'])
    friends_data = friends_resp.json() if friends_resp and friends_resp.status_code == 200 else {}
    
    # Let's build a complete list of people "already online"
    # 1. Confirmed friends (friends_data['friends'] is a list of {username, online} objects)
    confirmed_friends = [f['username'] for f in friends_data.get('friends', [])]
    
    #2. Pending requests (these are lists of strings)
    sent_requests = friends_data.get('pending_sent', [])
    received_requests = friends_data.get('pending_received', [])
    
    #3. Let's put it all together + ourselves
    all_contacts = confirmed_friends + sent_requests + received_requests + [session['username']]
    
    return render_template('history.html', user=session['username'], history=history, current_friends=all_contacts)

@app.route('/match/analyze/<match_id>')
def match_analyze(match_id):
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("GET", f"/history/match/{match_id}", token=session['token'])
    if not resp or resp.status_code != 200:
        flash("Error loading match details.")
        return redirect(url_for('dashboard'))
    match_data = resp.json()
    return render_template('match_details.html', user=session['username'], match=match_data)

# --- LOGICA MATCH & GAMEPLAY ---

@app.route('/create_match', methods=['POST'])
def create_match():
    if 'token' not in session: return redirect(url_for('index'))
    opponent = request.form.get('opponent')
    
    if opponent == "CPU" or opponent == "Guest":
        endpoint = "/matches"
    else:
        endpoint = "/invites"
        
    resp = api_request("POST", endpoint, 
                       data={"player1": session['username'], "player2": opponent}, 
                       token=session['token'])
    
    if resp and resp.status_code == 201:
        if opponent == "CPU":
            return redirect(url_for('game', match_id=resp.json()['match_id']))
        elif opponent == "Guest":
            # Local game requires the parameter 'local=1'
            return redirect(url_for('game', match_id=resp.json()['match_id'], local=1)) 
        else:
            flash(f"Challenge sent to {opponent}! Waiting for acceptance.")
            return redirect(url_for('dashboard'))
    else:
        flash("Could not send challenge.")
        return redirect(url_for('dashboard'))

@app.route('/create_match_cpu', methods=['POST'])
def create_match_cpu():
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("POST", "/matches", data={"player1": session['username'], "player2": "CPU"}, token=session['token'])
    if resp and resp.status_code == 201:
        return redirect(url_for('game', match_id=resp.json()['match_id']))
    else:
        flash("Could not create match vs CPU.")
        return redirect(url_for('dashboard'))

@app.route('/create_match_local', methods=['POST'])
def create_match_local():
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("POST", "/matches", data={"player1": session['username'], "player2": "Guest"}, token=session['token'])
    
    if resp and resp.status_code == 201:
        return redirect(url_for('game', match_id=resp.json()['match_id'], local=1))
    else:
        flash("Could not create local match.")
        return redirect(url_for('dashboard'))

@app.route('/invite/accept/<match_id>')
def accept_invite(match_id):
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("POST", f"/invites/{match_id}/accept", data={"player": session['username']}, token=session['token'])
    if resp and resp.status_code == 200:
        return redirect(url_for('game', match_id=match_id))
    else:
        flash("Error accepting invite.")
        return redirect(url_for('dashboard'))

@app.route('/invite/reject/<match_id>')
def reject_invite(match_id):
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("POST", f"/invites/{match_id}/reject", data={"player": session['username']}, token=session['token'])
    flash("Invite rejected.")
    return redirect(url_for('dashboard'))

@app.route('/game/<match_id>')
def game(match_id):
    if 'token' not in session: return redirect(url_for('index'))
    is_local = request.args.get('local', '0') == '1'
    resp = api_request("GET", f"/matches/{match_id}", params={"player": session['username']}, token=session['token'])
    if not resp or resp.status_code != 200:
        flash("Error loading match.")
        return redirect(url_for('dashboard'))
    
    friends_resp = api_request("GET", f"/friends/list/{session['username']}", token=session['token'])
    friends_data = friends_resp.json() if friends_resp and friends_resp.status_code == 200 else {}
    
    # Here too, we use the full list to hide the buttons correctly
    confirmed = [f['username'] for f in friends_data.get('friends', [])]
    sent = friends_data.get('pending_sent', [])
    received = friends_data.get('pending_received', [])
    current_friends = confirmed + sent + received + [session['username']]
    
    return render_template('game.html', match_id=match_id, user=session['username'], local=is_local, current_friends=current_friends)

@app.route('/surrender/<match_id>', methods=['POST'])
def surrender(match_id):
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("POST", f"/matches/{match_id}/surrender", data={"player": session['username']}, token=session['token'])
    if resp and resp.status_code == 200:
        flash("You surrendered the match.")
    else:
        flash("Error surrendering match.")
    return redirect(url_for('dashboard'))

@app.route('/api/proxy/match/<match_id>')
def proxy_match_state(match_id):
    if 'token' not in session: return {"error": "Unauthorized"}, 401
    resp = api_request("GET", f"/matches/{match_id}", params={"player": session['username']}, token=session['token'])
    return resp.json(), resp.status_code

@app.route('/api/proxy/play/<match_id>', methods=['POST'])
def proxy_play(match_id):
    if 'token' not in session: return {"error": "Unauthorized"}, 401
    data = request.get_json()
    resp = api_request("POST", f"/matches/{match_id}/play", data=data, token=session['token'])
    return resp.json(), resp.status_code

@app.route('/api/proxy/match/<match_id>/react', methods=['POST'])
def proxy_react(match_id):
    if 'token' not in session: return {"error": "Unauthorized"}, 401
    data = request.get_json()
    # Enviamos la reacción al API Gateway para que llegue al match-service
    resp = api_request("POST", f"/matches/{match_id}/react", data=data, token=session['token'])
    return resp.json(), resp.status_code

@app.route('/matchmaking/join', methods=['POST'])
def matchmaking_join():
    if 'token' not in session: return redirect(url_for('index'))
    resp = api_request("POST", "/matchmaking/join", data={"player": session['username']}, token=session['token'])
    if resp and resp.status_code == 200:
        data = resp.json()
        if data['status'] == 'matched':
            return redirect(url_for('game', match_id=data['match_id']))
        elif data['status'] == 'waiting':
            return redirect(url_for('matchmaking_waiting'))
    flash("Matchmaking error.")
    return redirect(url_for('dashboard'))

@app.route('/matchmaking/waiting')
def matchmaking_waiting():
    if 'token' not in session: return redirect(url_for('index'))
    return render_template('waiting.html', user=session['username'])

@app.route('/api/proxy/matchmaking/status')
def proxy_matchmaking_status():
    if 'token' not in session: return {"error": "Unauthorized"}, 401
    resp = api_request("GET", f"/matchmaking/status/{session['username']}", token=session['token'])
    return resp.json(), resp.status_code

@app.route('/matchmaking/cancel', methods=['POST'])
def matchmaking_cancel():
    if 'token' not in session: return redirect(url_for('index'))
    api_request("POST", "/matchmaking/leave", data={"player": session['username']}, token=session['token'])
    return redirect(url_for('dashboard'))

@app.route('/friends')
def friends_page():
    if 'token' not in session: return redirect(url_for('index'))
    send_heartbeat()
    resp = api_request("GET", f"/friends/list/{session['username']}", token=session['token'])
    friends_data = resp.json() if resp and resp.status_code == 200 else {}
    return render_template('friends.html', 
                           user=session['username'],
                           friends=friends_data.get('friends', []),
                           received=friends_data.get('pending_received', []),
                           sent=friends_data.get('pending_sent', []))

@app.route('/friends/add', methods=['POST'])
def add_friend():
    if 'token' not in session: return redirect(url_for('index'))
    target = request.form.get('username')
    resp = api_request("POST", "/friends/request", 
                       data={"sender": session['username'], "target": target},
                       token=session['token'])
    if resp and resp.status_code == 201:
        flash(f"Friend request sent to {target}")
    else:
        err = resp.json().get('error') if resp else "Error"
        flash(f"Failed: {err}")
    return redirect(url_for('friends_page'))

@app.route('/friends/accept/<requester>')
def accept_friend(requester):
    if 'token' not in session: return redirect(url_for('index'))
    api_request("POST", "/friends/response", data={"user": session['username'], "requester": requester, "action": "accept"}, token=session['token'])
    flash(f"You are now friends with {requester}")
    return redirect(url_for('friends_page'))

@app.route('/friends/reject/<requester>')
def reject_friend(requester):
    if 'token' not in session: return redirect(url_for('index'))
    api_request("POST", "/friends/response", data={"user": session['username'], "requester": requester, "action": "reject"}, token=session['token'])
    flash("Request rejected")
    return redirect(url_for('friends_page'))

@app.route('/friends/remove/<friend>')
def remove_friend(friend):
    if 'token' not in session: return redirect(url_for('index'))
    api_request("POST", "/friends/remove", data={"user": session['username'], "friend": friend}, token=session['token'])
    flash(f"Removed {friend} from friends.")
    return redirect(url_for('friends_page'))

@app.route('/admin')
def admin_redirect():
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == ASMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid Admin Credentials")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    service_status = {}
    # Key services to check your status
    for service_key, endpoint in [
        ('Auth', '/auth/health'),
        ('Player', '/players/health'),
        ('Cards', '/cards/health'),
        ('Match', '/matches/health'),
        ('History', '/history/health')
    ]:
        resp = api_request("GET", endpoint)
        if resp and resp.status_code == 200:
            service_status[service_key] = " Healthy"
        elif resp and resp.status_code == 503:
            service_status[service_key] = " Gateway Error (Service likely down)"
        else:
            service_status[service_key] = " Unhealthy/Down"

    # Existing code to fetch data
    users_resp = api_request("GET", "/auth/users")
    users = users_resp.json() if users_resp and users_resp.status_code == 200 else []
    
    players_resp = api_request("GET", "/players/list/all")
    players = players_resp.json() if players_resp and players_resp.status_code == 200 else []
    
    cards_resp = api_request("GET", "/cards/cards")
    cards = []
    if cards_resp and cards_resp.status_code == 200:
        raw_cards = cards_resp.json()
        cards = [enrich_card_with_image(c) for c in raw_cards]
        
    return render_template('admin_dashboard.html', 
                           users=users, 
                           players=players, 
                           cards=cards,
                           service_status=service_status)
    
if __name__ == '__main__':
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)