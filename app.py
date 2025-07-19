#!/usr/bin/env python3
"""
Azul Game - Main Flask Application
A simplified two-player Azul implementation: Human vs Computer AI
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import copy

app = Flask(__name__)
app.secret_key = 'azul_game_secret'

# Game Constants
TILE_TYPES = ['blue', 'yellow', 'red', 'black', 'white']
COLORS = TILE_TYPES
NUM_FACTORIES = 5  # For 2 players
TILES_PER_FACTORY = 4
PATTERN_LINE_SIZES = [1, 2, 3, 4, 5]
WALL_PATTERN = [
    ['blue', 'yellow', 'red', 'black', 'white'],
    ['white', 'blue', 'yellow', 'red', 'black'],
    ['black', 'white', 'blue', 'yellow', 'red'],
    ['red', 'black', 'white', 'blue', 'yellow'],
    ['yellow', 'red', 'black', 'white', 'blue']
]

@dataclass
class PlayerBoard:
    """Represents a player's board with pattern lines, wall, and floor line"""
    pattern_lines: List[List[str]]  # 5 lines of increasing size
    wall: List[List[bool]]  # 5x5 grid of placed tiles
    floor_line: List[str]  # Penalty tiles
    score: int = 0
    
    def __init__(self):
        self.pattern_lines = [[] for _ in range(5)]
        self.wall = [[False] * 5 for _ in range(5)]
        self.floor_line = []
        self.score = 0

    def can_place_in_pattern_line(self, row: int, color: str, count: int) -> bool:
        """Check if tiles can be placed in a pattern line"""
        if row < 0 or row >= 5:
            return False

        pattern_line = self.pattern_lines[row]
        max_size = PATTERN_LINE_SIZES[row]

        # Check if line is already full
        if len(pattern_line) >= max_size:
            return False

        # Check if line is empty or contains same color
        if pattern_line and pattern_line[0] != color:
            return False

        # Check if this color is already on the wall for this row
        wall_col = WALL_PATTERN[row].index(color)
        if self.wall[row][wall_col]:
            return False

        return True

    def place_tiles(self, row: int, color: str, count: int):
        """Place tiles in pattern line or floor line"""
        if row == -1:  # Floor line
            self.floor_line.extend([color] * count)
        else:
            pattern_line = self.pattern_lines[row]
            max_size = PATTERN_LINE_SIZES[row]
            
            # Add tiles to pattern line
            tiles_to_add = min(count, max_size - len(pattern_line))
            pattern_line.extend([color] * tiles_to_add)
            
            # Excess tiles go to floor
            excess = count - tiles_to_add
            if excess > 0:
                self.floor_line.extend([color] * excess)
    
    def get_valid_moves(self, color: str, count: int) -> List[int]:
        """Get list of valid pattern line indices for placing tiles"""
        valid_moves = []
        
        # Check each pattern line
        for row in range(5):
            if self.can_place_in_pattern_line(row, color, count):
                valid_moves.append(row)
        
        # Floor line is always valid
        valid_moves.append(-1)
        
        return valid_moves

class GameState:
    """Manages the complete game state"""
    
    def __init__(self):
        self.factories = [[] for _ in range(NUM_FACTORIES)]
        self.center = []
        self.players = [PlayerBoard(), PlayerBoard()]
        self.current_player = 0
        self.round_num = 1
        self.tile_bag = []
        self.discard_pile = []
        self.first_player_token = True  # True if in center
        self.game_over = False
        self.winner = None
        
        self.setup_new_game()
    
    def setup_new_game(self):
        """Initialize a new game"""
        self.tile_bag = TILE_TYPES * 20  # 20 of each color
        random.shuffle(self.tile_bag)
        self.setup_round()
    
    def setup_round(self):
        """Setup factories for a new round"""
        self.factories = [[] for _ in range(NUM_FACTORIES)]
        self.center = []
        self.first_player_token = True
        
        # Fill factories
        for factory in self.factories:
            for _ in range(TILES_PER_FACTORY):
                if self.tile_bag:
                    factory.append(self.tile_bag.pop())
                elif self.discard_pile:
                    # Refill bag from discard pile
                    self.tile_bag = self.discard_pile.copy()
                    random.shuffle(self.tile_bag)
                    self.discard_pile = []
                    if self.tile_bag:
                        factory.append(self.tile_bag.pop())
    
    def get_available_moves(self) -> List[Dict]:
        """Get all valid moves for current player"""
        moves = []
        player = self.players[self.current_player]
        
        # Check factory displays
        for factory_idx, factory in enumerate(self.factories):
            if not factory:
                continue
            
            color_counts = defaultdict(int)
            for tile in factory:
                color_counts[tile] += 1
            
            for color, count in color_counts.items():
                valid_rows = player.get_valid_moves(color, count)
                for row in valid_rows:
                    moves.append({
                        'source': 'factory',
                        'source_idx': factory_idx,
                        'color': color,
                        'count': count,
                        'target_row': row
                    })
        
        # Check center display
        if self.center:
            color_counts = defaultdict(int)
            for tile in self.center:
                color_counts[tile] += 1
            
            for color, count in color_counts.items():
                valid_rows = player.get_valid_moves(color, count)
                for row in valid_rows:
                    moves.append({
                        'source': 'center',
                        'source_idx': 0,
                        'color': color,
                        'count': count,
                        'target_row': row
                    })
        
        return moves
    
    def make_move(self, move: Dict):
        """Execute a move"""
        player = self.players[self.current_player]
        
        if move['source'] == 'factory':
            factory = self.factories[move['source_idx']]
            
            # Take tiles of chosen color
            taken_tiles = [tile for tile in factory if tile == move['color']]
            remaining_tiles = [tile for tile in factory if tile != move['color']]
            
            # Move remaining tiles to center
            self.center.extend(remaining_tiles)
            
            # Clear factory
            self.factories[move['source_idx']] = []
            
        else:  # center
            # Take tiles of chosen color
            taken_tiles = [tile for tile in self.center if tile == move['color']]
            remaining_tiles = [tile for tile in self.center if tile != move['color']]
            
            # Check for first player token
            if self.first_player_token:
                player.floor_line.append('first_player')
                self.first_player_token = False
                self.current_player = 0  # This player goes first next round
            
            # Update center
            self.center = remaining_tiles
        
        # Place tiles on player board
        player.place_tiles(move['target_row'], move['color'], len(taken_tiles))
        
        # Check if round is over
        if self.is_round_over():
            self.end_round()
        else:
            self.current_player = 1 - self.current_player
    
    def is_round_over(self) -> bool:
        """Check if all factories and center are empty"""
        for factory in self.factories:
            if factory:
                return False
        return len(self.center) == 0
    
    def end_round(self):
        """Process end of round: move tiles to wall, score, check end game"""
        for player_idx, player in enumerate(self.players):
            # Move complete pattern lines to wall
            for row in range(5):
                pattern_line = player.pattern_lines[row]
                if len(pattern_line) == PATTERN_LINE_SIZES[row]:
                    color = pattern_line[0]
                    wall_col = WALL_PATTERN[row].index(color)
                    player.wall[row][wall_col] = True
                    
                    # Score the tile
                    player.score += self.calculate_tile_score(player, row, wall_col)
                    
                    # Discard excess tiles
                    self.discard_pile.extend(pattern_line[1:])
                    player.pattern_lines[row] = []
            
            # Score floor line penalties
            floor_penalties = [1, 1, 2, 2, 2, 3, 3]
            for i, tile in enumerate(player.floor_line):
                if i < len(floor_penalties):
                    player.score -= floor_penalties[i]
            
            # Discard floor line tiles
            self.discard_pile.extend([tile for tile in player.floor_line if tile != 'first_player'])
            player.floor_line = []
            
            # Ensure score doesn't go negative
            player.score = max(0, player.score)
        
        # Check for game end
        if self.is_game_over():
            self.final_scoring()
            self.game_over = True
        else:
            self.round_num += 1
            self.setup_round()
    
    def calculate_tile_score(self, player: PlayerBoard, row: int, col: int) -> int:
        """Calculate score for placing a tile"""
        score = 1
        
        # Check horizontal connections
        left = col - 1
        while left >= 0 and player.wall[row][left]:
            score += 1
            left -= 1
        
        right = col + 1
        while right < 5 and player.wall[row][right]:
            score += 1
            right += 1
        
        # Check vertical connections
        up = row - 1
        while up >= 0 and player.wall[up][col]:
            score += 1
            up -= 1
        
        down = row + 1
        while down < 5 and player.wall[down][col]:
            score += 1
            down += 1
        
        return score
    
    def is_game_over(self) -> bool:
        """Check if any player has completed a row"""
        for player in self.players:
            for row in player.wall:
                if all(row):
                    return True
        return False
    
    def final_scoring(self):
        """Apply final scoring bonuses"""
        for player in self.players:
            # Horizontal line bonuses
            for row in player.wall:
                if all(row):
                    player.score += 2
            
            # Vertical line bonuses
            for col in range(5):
                if all(player.wall[row][col] for row in range(5)):
                    player.score += 7
            
            # Color bonuses
            for color_idx, color in enumerate(TILE_TYPES):
                if all(player.wall[row][WALL_PATTERN[row].index(color)] for row in range(5)):
                    player.score += 10
        
        # Determine winner
        if self.players[0].score > self.players[1].score:
            self.winner = 0
        elif self.players[1].score > self.players[0].score:
            self.winner = 1
        else:
            self.winner = 0  # Tie goes to player 0

# Global game instance
game = GameState()

# AI Logic
class SimpleAI:
    """Simple random AI that picks valid moves randomly"""
    
    @staticmethod
    def get_move(game_state: GameState) -> Dict:
        """Get a random valid move"""
        moves = game_state.get_available_moves()
        if not moves:
            return None
        return random.choice(moves)

# Flask Routes
@app.route('/')
def index():
    """Main game page"""
    return render_template('game.html', game=game, enumerate=enumerate, WALL_PATTERN=WALL_PATTERN)

@app.route('/new_game', methods=['POST'])
def new_game():
    """Start a new game"""
    global game
    game = GameState()
    return redirect(url_for('index'))

@app.route('/make_move', methods=['POST'])
def make_move():
    """Handle human player move"""
    if game.game_over or game.current_player != 0:
        return redirect(url_for('index'))
    
    source = request.form.get('source')
    source_idx = int(request.form.get('source_idx'))
    color = request.form.get('color')
    target_row = int(request.form.get('target_row'))
    
    # Find matching move
    moves = game.get_available_moves()
    for move in moves:
        if (move['source'] == source and move['source_idx'] == source_idx and 
            move['color'] == color and move['target_row'] == target_row):
            game.make_move(move)
            break
    
    return redirect(url_for('index'))

@app.route('/ai_move', methods=['POST'])
def ai_move():
    """Handle AI move"""
    if game.game_over or game.current_player != 1:
        return redirect(url_for('index'))
    
    ai_move = SimpleAI.get_move(game)
    if ai_move:
        game.make_move(ai_move)
    
    return redirect(url_for('index'))

@app.route('/game_state')
def game_state():
    """API endpoint for game state (for AJAX updates)"""
    return jsonify({
        'current_player': game.current_player,
        'round_num': game.round_num,
        'game_over': game.game_over,
        'winner': game.winner,
        'scores': [p.score for p in game.players]
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
