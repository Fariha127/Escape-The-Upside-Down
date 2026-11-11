"""Central configuration. Every balance value lives here (no magic numbers elsewhere)."""

# --- Map ---
GRID_SIZE = 15

# --- Eleven ---
MAX_HP = 5
START_POWER = 1
MAX_POWER = 15

# --- Combat (used from Phase 4) ---
DEMOGORGON_DAMAGE = 1
VECNA_DAMAGE = 2
DEMOGORGON_ATTACK_COST = 1
DEMOGORGON_REWARD = 3
DEMOGORGON_COOLDOWN = 1          # decision: 1-turn cooldown after a hit (simpler than knockback)
FINAL_POWER_REQUIREMENT = 10

# --- Abilities (used from Phase 4) ---
ABILITY_USES = {"RADAR": 2, "SPEED": 1, "TELEPORT": 1, "FREEZE": 1}
ABILITY_DURATIONS = {"SPEED": 3, "FREEZE": 2}
FRIEND_ABILITY = {"Dustin": "RADAR", "Lucas": "SPEED", "Mike": "TELEPORT", "Will": "FREEZE"}

# --- AI parameters (used from Phase 3+) ---
MINIMAX_DEPTH = 4
ELEVEN_MCTS_SIMULATIONS = 300
MINDFLAYER_MCTS_SIMULATIONS = 150
MCTS_EXPLORATION = 1.41
MCTS_ROLLOUT_DEPTH = 15

# --- Game flow ---
MAX_TURNS = 150
RNG_SEED = 42

# --- Characters (Phase 2) ---
RESCUE_RANGE = 1                  # Manhattan distance within which Eleven can rescue a friend
MAX_NORMAL_DEMOGORGONS = 10       # hard cap for normal (power-giving) Demogorgons
MAX_TEMP_CREATURES = 3            # cap on simultaneous Mind-Flayer-spawned creatures
FINAL_ATTACK_CONSUMES_POWER = True

# --- Phase 4: combat, hazards, abilities ---
ATTACK_RANGE = 1                 # Eleven can attack a Demogorgon within this Manhattan distance
HAZARD_DAMAGE = 1                # HP lost each time Eleven ENTERS a hazard cell
RADAR_DURATION = 3               # turns Dustin's Radar report stays on after it is used
SPEED_MOVES_PER_TURN = 2         # Eleven's moves per turn while Speed is active
TELEPORT_SAFE_DISTANCE = 3       # a Teleport cell must be at least this far (Manhattan) from every enemy
RESCUE_POWER_BONUS = 3           # power Eleven gains each time she rescues a friend (4 friends = 12)

# --- Phase 5: Vecna (Minimax + Alpha-Beta) ---
VECNA_ATTACK_RANGE = 1           # Vecna hits Eleven when within this Manhattan distance (no cooldown in the spec)
VECNA_USE_ALPHA_BETA = True      # False = plain Minimax (used by the experiments)
VECNA_EVAL_DISTANCE_CAP = 30     # walking distance at which "closeness" counts as zero (2 * GRID_SIZE)
VECNA_EVAL_WEIGHTS = {           # Vecna's evaluation of a NON-terminal state (always kept inside -49..+49)
    "HP_LOST": 8,                # per HP Eleven has lost
    "PROXIMITY": 6,              # up to this much when Vecna stands next to Eleven
    "RESCUED": 2,                # subtracted per rescued friend (Eleven's progress)
    "PORTAL_PROGRESS": 4,        # subtracted up to this much when the portal is open and Eleven is near it
}

# --- Phase 6: Eleven (MCTS picks a strategic goal, A* walks to it) ---
MCTS_GOAL_TURNS = 6              # most turns one goal may run inside a simulation (= one tree edge)
ELEVEN_REPLAN_TURNS = 4          # real game: a goal is kept at most this many turns before MCTS re-plans
ELEVEN_DANGER_DISTANCE = 2       # an enemy this close (walking distance) is "danger": VECNA_DANGER reward, re-plan trigger
DANGER_STEP_COST = 5             # extra path cost of a cell where an enemy could hit Eleven this turn
EVADE_OPEN_WEIGHT = 3            # EVADE prefers open areas over dead ends: up to this many cells of 'safety' bonus
EVADE_RADIUS = 6                 # EVADE looks for a safe cell within this walking distance
AI_TURN_DELAY_MS = 600           # AI-vs-AI: pause between turns at 1x speed
AI_SPEEDS = (0.5, 1, 2, 4)       # AI-vs-AI speed multipliers

# --- A* (Phase 3) ---
ASTAR_HAZARD_COST = 3     # Eleven's A* treats hazard cells as costlier (>=1 keeps Manhattan admissible)

# --- Utilities and rewards (scaled down: 1-2 digit numbers; only ratios matter) ---
UTILITY_WIN = 50                 # terminal: Eleven escapes
UTILITY_LOSS = -50               # terminal: Eleven dies or the turn limit is reached
ELEVEN_REWARDS = {               # Eleven's MCTS (Phase 6)
    "ESCAPE": 50, "DEFEAT_MIND_FLAYER": 25, "RESCUE_FRIEND": 10, "DEFEAT_DEMOGORGON": 2,
    "GAIN_POWER": 1, "LOSE_HP": -5, "VECNA_DANGER": -8, "DEATH": -50,
    "PROGRESS": 0.5,             # Phase 6 shaping: per cell gained toward the nearest objective (see ai/sim.py)
}
MIND_FLAYER_REWARDS = {          # Mind Flayer's MCTS (Phase 7)
    "KILL_ELEVEN": 50, "DAMAGE_ELEVEN": 10, "BLOCK_ROUTE": 5, "TRAP_ELEVEN": 4,
    "FORCE_AWAY": 3, "ELEVEN_ESCAPES": -50,
}
MCTS_REWARD_SCALE = 50           # MCTS divides rewards by this so UCB1's constant (1.41) still fits