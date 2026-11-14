"""Central configuration. Every balance value lives here (no magic numbers elsewhere)."""

# --- Map ---
GRID_SIZE = 15

# --- Eleven ---
MAX_HP = 5
START_POWER = 1
MAX_POWER = 15

# --- Combat ---
DEMOGORGON_DAMAGE = 1
VECNA_DAMAGE = 2
DEMOGORGON_ATTACK_COST = 1
DEMOGORGON_REWARD = 3
DEMOGORGON_COOLDOWN = 1          # decision: 1-turn cooldown after a hit (simpler than knockback)
FINAL_POWER_REQUIREMENT = 10

# --- Abilities (used from Phase 4) ---
ABILITY_USES = {"SPEED": 1, "TELEPORT": 1, "FREEZE": 1}
ABILITY_DURATIONS = {"SPEED": 3, "FREEZE": 2}

# --- AI parameters ---
MINIMAX_DEPTH = 4
ELEVEN_MCTS_SIMULATIONS = 300
MINDFLAYER_MCTS_SIMULATIONS = 150
MCTS_EXPLORATION = 1.41
MCTS_ROLLOUT_DEPTH = 15

# --- Game flow ---
MAX_TURNS = 150
RNG_SEED = 42
RANDOM_SEED_PER_GAME = True      # UI: every new game gets its own seed (shown on screen); False = always RNG_SEED

# --- Characters ---
RESCUE_RANGE = 1                  # Manhattan distance within which Eleven can rescue a friend
MAX_NORMAL_DEMOGORGONS = 10       # hard cap for normal (power-giving) Demogorgons
MAX_TEMP_CREATURES = 3            # cap on simultaneous Mind-Flayer-spawned creatures
FINAL_ATTACK_CONSUMES_POWER = True

# --- combat, hazards, abilities ---
ATTACK_RANGE = 1                 # Eleven can attack a Demogorgon within this Manhattan distance
HAZARD_DAMAGE = 1                # HP lost each time Eleven ENTERS a hazard cell
SPEED_MOVES_PER_TURN = 2         # Eleven's moves per turn while Speed is active
TELEPORT_SAFE_DISTANCE = 3       # a Teleport cell must be at least this far (Manhattan) from every enemy
RESCUE_POWER_BONUS = 4           # power Eleven gains per rescue (balance: was 3; 4 friends = 16, capped at MAX_POWER)

# --- Vecna (Minimax + Alpha-Beta) ---
VECNA_ATTACK_RANGE = 1           # Vecna hits Eleven when within this Manhattan distance (no cooldown in the spec)
VECNA_USE_ALPHA_BETA = True      # False = plain Minimax (used by the experiments)
VECNA_EVAL_DISTANCE_CAP = 30     # walking distance at which "closeness" counts as zero (2 * GRID_SIZE)
VECNA_EVAL_WEIGHTS = {           # Vecna's evaluation of a NON-terminal state (always kept inside -49..+49)
    "HP_LOST": 8,                # per HP Eleven has lost
    "PROXIMITY": 6,              # up to this much when Vecna stands next to Eleven
    "RESCUED": 2,                # subtracted per rescued friend (Eleven's progress)
    "PORTAL_PROGRESS": 4,        # subtracted up to this much when the portal is open and Eleven is near it
}

# --- Eleven (MCTS picks a strategic goal, A* walks to it) ---
MCTS_GOAL_TURNS = 6              # most turns one goal may run inside a simulation (= one tree edge)
ELEVEN_RESCUE_WILL_LAST = True   # Will wakes the Mind Flayer, so Eleven only offers 'rescue Will' once the other friends are saved
ELEVEN_REPLAN_TURNS = 2          # real game: a goal is kept at most this many turns before MCTS re-plans (balance: was 4)
ELEVEN_ABILITIES_ONLY_IN_DANGER = True   # the AI only offers Speed / Teleport / Freeze as goals while an enemy is close (each ability is single-use)
ELEVEN_ABILITY_DANGER_DISTANCE = 3       # "close" for the rule above: walking steps to the nearest enemy
ELEVEN_DANGER_DISTANCE = 2       # an enemy this close (walking distance) is "danger": VECNA_DANGER reward, re-plan trigger
DANGER_STEP_COST = 5             # extra path cost of a cell where an enemy could hit Eleven this turn
EVADE_OPEN_WEIGHT = 3            # EVADE prefers open areas over dead ends: up to this many cells of 'safety' bonus
EVADE_RADIUS = 6                 # EVADE looks for a safe cell within this walking distance
AI_TURN_DELAY_MS = 600           # AI-vs-AI: pause between turns at 1x speed
AI_SPEEDS = (0.5, 1, 2, 4)       # AI-vs-AI speed multipliers
ANIM_ENABLED = True              # UI: characters slide between cells, hits and kills flash
ANIM_SLIDE_MS = 140              # length of one slide
ANIM_FLASH_MS = 320              # length of a hit / kill flash
ANIM_MIN_MS = 40                 # a slide shorter than this is skipped (very fast AI-vs-AI)
ANIM_TURN_FRACTION = 0.7         # AI-vs-AI: a slide may use at most this share of one turn's delay
ANIM_MAX_SLIDE_CELLS = 2         # longer jumps (Teleport) are instant
SOUND_ENABLED = True             # UI: sound effects on/off (also a Settings row)
SOUND_VOLUME = 0.4               # 0.0 - 1.0
SOUND_SAMPLE_RATE = 22050        # Hz of the generated tones

# --- Flayer (MCTS: corrupt cells, summon creatures) ---
MF_CORRUPT_DURATION = 2          # full turns a corrupted cell blocks everyone
MF_MAX_CORRUPTED = 4             # most corrupted cells at the same time
MF_SPAWN_COOLDOWN = 4            # turns between two summons
MF_HORIZON = 6                   # turns the Mind Flayer's MCTS looks ahead (tree + rollout)
MF_ROUTE_LOOKAHEAD = 6           # corrupt candidates: the first cells of Eleven's expected route
MF_MAX_CORRUPT_CANDIDATES = 8    # most corrupt actions the search considers at one node
MF_SPAWN_CANDIDATES = 3          # most summon cells the search considers at one node
MF_SPAWN_MIN_DISTANCE = 2        # a summoned creature appears this far from Eleven (walking distance) ...
MF_SPAWN_MAX_DISTANCE = 4        # ... up to this far
MF_TRAP_FREE_NEIGHBOURS = 1      # Eleven counts as trapped when she can enter at most this many neighbour cells

# --- A* ---
ASTAR_HAZARD_COST = 3     # Eleven's A* treats hazard cells as costlier (>=1 keeps Manhattan admissible)

# --- Utilities and rewards (scaled down: 1-2 digit numbers; only ratios matter) ---
UTILITY_WIN = 50                 # terminal: Eleven escapes
UTILITY_LOSS = -50               # terminal: Eleven dies or the turn limit is reached
ELEVEN_REWARDS = {               # Eleven's MCTS 
    "ESCAPE": 50, "DEFEAT_MIND_FLAYER": 25, "RESCUE_FRIEND": 10, "DEFEAT_DEMOGORGON": 2,
    "GAIN_POWER": 1, "LOSE_HP": -5, "VECNA_DANGER": -8, "DEATH": -50,
    "PROGRESS": 0.5,             # shaping: per cell gained toward the nearest objective (see ai/sim.py)
}
MIND_FLAYER_REWARDS = {          # Mind Flayer's MCTS
    "KILL_ELEVEN": 50, "DAMAGE_ELEVEN": 10, "BLOCK_ROUTE": 5, "TRAP_ELEVEN": 4,
    "FORCE_AWAY": 3, "ELEVEN_ESCAPES": -50,
    "DEFEATED": -25,             # addition: Eleven's final attack beats the Mind Flayer
}
MCTS_REWARD_SCALE = 50           # MCTS divides rewards by this so UCB1's constant (1.41) still fits
# --- random board: the walls are fixed, the placements are random (see game/board_gen.py) ---
RANDOM_BOARD_PER_GAME = True     # UI: every new game gets a board generated from its seed; False = the fixed default map
DEMOGORGON_COUNT = 2             # normal Demogorgons on a generated board (cap: MAX_NORMAL_DEMOGORGONS); measured on 100 random boards: 2 -> ~47% wins, 3 -> ~33%, 4 -> ~22%, 6 -> ~13%
BOARD_HAZARD_COUNT = 3           # hazard cells placed on a generated board
BOARD_PORTAL_MIN_DIST = 20       # portal is at least this many steps from Eleven's start (default map: 25)
BOARD_FRIEND_MIN_DIST_ELEVEN = 8     # each friend at least this far from Eleven's start (default map: 9)
BOARD_FRIEND_MIN_DIST_VECNA = 6      # ... and from Vecna's start
BOARD_FRIEND_SPACING = 6         # friends at least this far from each other (default map: 7)
BOARD_DEMOGORGON_MIN_DIST_ELEVEN = 6 # Demogorgons start at least this far from Eleven (default map: 6)
BOARD_DEMOGORGON_SPACING = 4     # Demogorgons at least this far from each other (default map: 5)
BOARD_DEMOGORGON_MIN_DIST_OBJECT = 3 # ... and from every friend and from the portal
BOARD_HAZARD_MIN_DIST_ELEVEN = 3     # hazards never start next to Eleven
BOARD_HAZARD_MAX_DETOUR = 2      # walking around a hazard costs at most this many extra steps between any two objectives
                                 # (Eleven's A* detours when that is cheaper than ASTAR_HAZARD_COST)
BOARD_MAX_TRIES = 500            # placement attempts before falling back to the default map
