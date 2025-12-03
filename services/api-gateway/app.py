from flask import Flask, jsonify, request
import requests
# Disable security warnings for self-signed certificates
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

app = Flask(__name__)

# Map of services UPDATED TO HTTPS
SERVICES = {
    "auth": "https://auth-service:5000",
    "cards": "https://cards-service:5000",
    "player": "https://player-service:5000",
    "match": "https://match-service:5000",
    "history": "https://history-service:5000"
}

@app.route('/health', methods=['GET'])
def gateway_health():
    return jsonify({"status": "gateway running (secure)"}), 200

# --- HELPER ---
def build_url(service_url, service_prefix, path):
    if path:
        return f"{service_url}/{service_prefix}/{path}"
    return f"{service_url}/{service_prefix}"

def forward_request(service_name, service_prefix, path):
    """Funzione helper centralizzata per l'inoltro"""
    url = build_url(SERVICES[service_name], service_prefix, path)
    params = request.args
    headers = {key: value for key, value in request.headers if key != 'Host'}
    
    try:
        # verify=False is crucial for self-signed certificates
        resp = requests.request(
            method=request.method,
            url=url,
            json=request.get_json() if request.is_json else None,
            headers=headers,
            params=params,
            verify=False 
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except requests.exceptions.ConnectionError:
        return jsonify({"error": f"{service_name} Service down"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- PROXIES ---

@app.route('/auth', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/auth/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_auth(path):
    return forward_request("auth", "auth", path)

@app.route('/cards', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/cards/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_cards(path):
    return forward_request("cards", "cards", path)

@app.route('/players', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/players/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_players(path):
    return forward_request("player", "players", path)

@app.route('/matches', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/matches/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_matches(path):
    return forward_request("match", "matches", path)

@app.route('/history', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/history/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_history(path):
    return forward_request("history", "history", path)

@app.route('/invites', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/invites/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_invites(path):
    return forward_request("match", "invites", path)

@app.route('/friends', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/friends/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_friends(path):
    return forward_request("player", "friends", path)

# --- New route for matchmaking ---
@app.route('/matchmaking', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/matchmaking/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_matchmaking(path):
    # Forward to the MATCH service, but use the "matchmaking" prefix
    # So the URL becomes: http://match-service:5000/matchmaking/join
    return forward_request("match", "matchmaking", path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=('../certs/cert.pem', '../certs/key.pem'))