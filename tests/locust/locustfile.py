from locust import HttpUser, task, between
import uuid
import random

class EscobaPlayer(HttpUser):
    # Waiting time between one action and another (simulates human thinking)
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Eseguito quando un utente virtuale "nasce".
        Si registra e fa il login per ottenere il token.
        """
        self.username = f"player_{str(uuid.uuid4())[:8]}"
        self.password = "password123"
        self.email = f"{self.username}@test.com"
        self.token = None

        # 1. Registration
        with self.client.post("/auth/register", json={
            "username": self.username,
            "password": self.password,
            "email": self.email
        }, catch_response=True) as response:
            if response.status_code == 409:
                response.success() # Ignore error if it already exists (in repeated tests)
            elif response.status_code != 201:
                response.failure(f"Registration failed: {response.text}")

        # 2. Login
        response = self.client.post("/auth/login", json={
            "username": self.username,
            "password": self.password
        })
        
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.user_id = response.json().get("user_id")
        else:
            print(f"Login failed for {self.username}")

    @task(1)
    def view_cards(self):
        """Peso 1: Ogni tanto guarda le carte"""
        if self.token:
            headers = {"Authorization": f"Bearer {self.token}"} # Header ready for when we implement verification
            self.client.get("/cards/cards", headers=headers)

    @task(2)
    def view_profile(self):
        """Peso 2: Guarda spesso il proprio profilo"""
        if self.token:
            self.client.get(f"/players/{self.username}")

    @task(3)
    def play_match_flow(self):
        """Peso 3: Ciclo partita (Crea match e controlla stato)"""
        if not self.token:
            return

        # Simulate a match against a fixed opponent (or self for testing)
        opponent = "luigi" 
        
        # Create match
        res = self.client.post("/matches", json={
            "player1": self.username,
            "player2": opponent
        })

        if res.status_code == 201:
            match_id = res.json().get("match_id")
            
            # Control the match state 3 times (simulate turns)
            for _ in range(3):
                self.client.get(f"/matches/{match_id}?player={self.username}")
                # Here we could add self.client.post(...) to play cards