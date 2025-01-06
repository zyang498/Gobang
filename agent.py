import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import random
import os
from model import GobangNet

class DQNAgent:
    def __init__(self, board_size=15, memory_size=10000, batch_size=64, gamma=0.99,
                 epsilon=1.0, epsilon_min=0.01, epsilon_decay=0.995, learning_rate=0.001):
        self.board_size = board_size
        self.action_size = board_size * board_size
        self.memory = deque(maxlen=memory_size)
        self.batch_size = batch_size
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = GobangNet(board_size).to(self.device)
        self.target_model = GobangNet(board_size).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        
        self.update_target_model()

    def update_target_model(self):
        self.target_model.load_state_dict(self.model.state_dict())

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def remember_batch(self, states, actions, rewards, next_states, dones):
        """Add a batch of experiences to memory"""
        for s, a, r, ns, d in zip(states, actions, rewards, next_states, dones):
            self.memory.append((s, a, r, ns, d))

    def act(self, state, valid_moves):
        if random.random() <= self.epsilon:
            return random.choice(valid_moves)
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        q_values = self.model(state_tensor).cpu().detach().numpy()[0]
        
        # Mask invalid moves with very low values
        valid_moves_mask = np.ones_like(q_values) * float('-inf')
        valid_moves_mask[valid_moves] = 0
        q_values = q_values + valid_moves_mask
        
        return np.argmax(q_values)

    def train(self):
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        states = torch.FloatTensor(np.array([x[0] for x in batch])).to(self.device)
        actions = torch.LongTensor(np.array([x[1] for x in batch])).to(self.device)
        rewards = torch.FloatTensor(np.array([x[2] for x in batch])).to(self.device)
        next_states = torch.FloatTensor(np.array([x[3] for x in batch])).to(self.device)
        dones = torch.FloatTensor(np.array([x[4] for x in batch])).to(self.device)

        current_q_values = self.model(states).gather(1, actions.unsqueeze(1))
        next_q_values = self.target_model(next_states).max(1)[0].detach()
        target_q_values = rewards + (1 - dones) * self.gamma * next_q_values

        loss = nn.MSELoss()(current_q_values.squeeze(), target_q_values)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save(self, filename):
        os.makedirs("checkpoint", exist_ok=True)
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon
        }, f"checkpoint/{filename}")

    def load(self, filename):
        checkpoint = torch.load(f"checkpoint/{filename}")
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.epsilon = checkpoint['epsilon']
        self.update_target_model() 