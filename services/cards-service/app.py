from flask import Flask, jsonify
import os

app = Flask(__name__)

# --- GENERAZIONE MAZZO ---
def generate_deck():
    """Genera i dati per le 40 carte con dettagli"""
    suits = ["Oros", "Copas", "Espadas", "Bastos"]
    # Mapping per i valori di gioco (La Scopa: 8,9,10 valgono 8,9,10)
    # Mapping per i nomi (1-7 sono numeri, 8=Sota, 9=Caballo, 10=Rey)
    deck = []
    card_id = 1
    
    for suit in suits:
        for i in range(1, 11): # 10 carte per seme
            # Determina il nome visuale
            name = str(i)
            if i == 8: name = "Sota (10)"
            elif i == 9: name = "Caballo (11)"
            elif i == 10: name = "Rey (12)"
            
            # Determina il valore per la somma 15
            game_value = i
            # In alcune varianti 8,9,10 valgono 8,9,10. In altre 8,9,10.
            # Usiamo i valori nominali del backend MatchService
            
            deck.append({
                "id": card_id,
                "suit": suit,
                "number": i, # 1-10
                "name": f"{name} de {suit}",
                "game_value": game_value
            })
            card_id += 1
    return deck

DECK = generate_deck()

@app.route('/cards/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "cards-service"}), 200

@app.route('/cards/cards', methods=['GET'])
def get_cards():
    return jsonify(DECK), 200

@app.route('/cards/cards/<int:card_id>', methods=['GET'])
def get_card(card_id):
    card = next((c for c in DECK if c["id"] == card_id), None)
    if card:
        return jsonify(card), 200
    return jsonify({"error": "Card not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)