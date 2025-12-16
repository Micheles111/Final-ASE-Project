from locust import HttpUser, task, between
import uuid
import random
import time # Added for time.sleep

class EscobaPlayer(HttpUser):
    # Waiting time between one action and another (simulates human thinking)
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Executed when a virtual user "spawns".
        It registers and logs in to get the token.
        """
        self.username = f"player_{str(uuid.uuid4())[:8]}"
        # MODIFICA QUI: Password complessa per soddisfare i requisiti del backend
        # (Maiuscola, Numero, Carattere Speciale, lunghezza 8-20)
        self.password = "Password123!" 
        self.email = f"{self.username}@test.com"
        self.token = None
        self.user_id = None # Initialize user_id

        # 1. Registration
        with self.client.post("/auth/register", json={
            "username": self.username,
            "password": self.password,
            "email": self.email
        }, catch_response=True, name="/auth/register [register/ignore_conflict]") as response:
            if response.status_code == 409:
                response.success() # Ignore error if it already exists (in repeated tests)
            elif response.status_code != 201:
                response.failure(f"Registration failed: {response.text}")

        # 2. Login
        response = self.client.post("/auth/login", json={
            "username": self.username,
            "password": self.password
        }, name="/auth/login") # Added name for clearer reporting
        
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.user_id = response.json().get("user_id")
        else:
            # Use Locust's logging instead of print for a clean log
            print(f"Login failed for {self.username}") 

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