from locust import HttpUser, task, between
import uuid
import random
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time # Added for time.sleep
import os
# Esto hace que la librería de Python ignore la verificación de SSL
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class EscobaPlayer(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # 1. Ignorar verificación SSL para certificados auto-firmados
        self.client.verify = False 
        
        # 2. Datos del usuario (CON MAYÚSCULA EN LA CONTRASEÑA)
        self.username = f"player_{str(uuid.uuid4())[:8]}"
        self.password = "Password123!" # <-- CAMBIADO: Añadida mayúscula
        self.email = f"{self.username}@test.com"
        self.token = None

        # Registro
        with self.client.post("/auth/register", json={
            "username": self.username,
            "password": self.password,
            "email": self.email
        }, catch_response=True, name="/auth/register") as response:
            if response.status_code == 201 or response.status_code == 409:
                response.success()
            else:
                response.failure(f"Registration failed: {response.text}")

        # Login
        response = self.client.post("/auth/login", json={
            "username": self.username,
            "password": self.password
        }, name="/auth/login")
        
        if response.status_code == 200:
            self.token = response.json().get('token')
            print(f"Login successful for {self.username}")
        else:
            print(f"Login failed for {self.username} with status {response.status_code}")
    @task(1)
    def view_cards(self):
        """Weight 1: Occasionally view the cards"""
        if self.token:
            headers = {"Authorization": f"Bearer {self.token}"}
            self.client.get("/cards/cards", headers=headers)

    @task(2)
    def view_profile(self):
        """Weight 2: Frequently view their own profile"""
        if self.token:
            self.client.get(f"/players/{self.username}")

    @task(3)
    def play_match_flow(self):
        """Weight 3: Match lifecycle (Create match and check status)"""
        if not self.token:
            return

        # Simulate a match against a fixed opponent (or self for testing)
        opponent = "luigi" 
        headers = {"Authorization": f"Bearer {self.token}"} # Use token for match operations if required
        
        # Create match
        res = self.client.post("/matches", json={
            "player1": self.username,
            "player2": opponent
        }, headers=headers)

        if res.status_code == 201:
            match_id = res.json().get("match_id")
            
            # Control the match state until it ends (Max 10 attempts)
            for attempt in range(10): 
                # Get the current game state
                match_response = self.client.get(
                    f"/matches/{match_id}?player={self.username}",
                    headers=headers
                )
                
                if match_response.status_code != 200:
                    break
                    
                match_state = match_response.json()
                
                # If the match has finished, break the loop
                if match_state.get('status') == 'finished':
                    break
                
                # If it's the player's turn, play a card
                if match_state.get('turn') == self.username:
                    player_hand = match_state.get('players', {}).get(
                        self.username, {}
                    ).get('hand', [])
                    
                    # If the player has cards and they are not hidden, play a random card
                    if player_hand and 'hidden' not in str(player_hand):
                        card_to_play = random.choice(player_hand)
                        
                        play_response = self.client.post(
                            f"/matches/{match_id}/play",
                            json={
                                "player": self.username,
                                "card_id": card_to_play
                            },
                            headers=headers
                        )
                        
                        # Log if there was a capture or escoba
                        if play_response.status_code == 200:
                            play_data = play_response.json()
                            if play_data.get('escoba'):
                                print(f"{self.username} scored an **ESCOBA**!")
                            elif play_data.get('captured'):
                                print(f"{self.username} captured {len(play_data['captured'])} cards")
                    else:
                        # Log if the hand is empty or cards are hidden (shouldn't happen on player's turn)
                        print(f"[{self.username} turn] Hand is empty or hidden, skipping play.") 
                else:
                    # It's not the player's turn, wait a bit
                    time.sleep(0.5)
        else:
            print(f"Match creation failed for {self.username}")