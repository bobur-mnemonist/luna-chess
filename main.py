import chess
import chess.engine
import random

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.core.text import LabelBase
from kivy.clock import Clock
from kivy.animation import Animation
import threading

try:
    LabelBase.register(name="ChessFont", fn_regular="assets/chess_merida_unicode.ttf")
    CHESS_FONT_NAME = "ChessFont"
except Exception:
    CHESS_FONT_NAME = None

# Text-to-speech (Android's built-in voice). If unavailable (e.g. desktop
# testing), the app should still work fine without voice.
try:
    from plyer import tts
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

# ============================================
# Unicode chess piece symbols
# ============================================

PIECE_SYMBOLS = {
    'P': '\u2659', 'N': '\u2658', 'B': '\u2657',
    'R': '\u2656', 'Q': '\u2655', 'K': '\u2654',
    'p': '\u265F', 'n': '\u265E', 'b': '\u265D',
    'r': '\u265C', 'q': '\u265B', 'k': '\u265A',
}

# ============================================
# Modern blue-gray color palette
# ============================================
LIGHT_SQUARE = (0.75, 0.80, 0.87, 1)
DARK_SQUARE = (0.29, 0.36, 0.46, 1)
SELECTED_SQUARE = (0.95, 0.75, 0.30, 1)
TARGET_SQUARE = (0.45, 0.70, 0.55, 1)
BG_COLOR = (0.10, 0.12, 0.16, 1)
PANEL_COLOR = (0.16, 0.19, 0.25, 1)


def piece_value(piece_type):
    values = {
        chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
        chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
    }
    return values.get(piece_type, 0)


CENTER_SQUARES = {chess.D4, chess.D5, chess.E4, chess.E5}
EXTENDED_CENTER = {chess.C3, chess.C4, chess.C5, chess.C6, chess.D3, chess.D6,
                    chess.E3, chess.E6, chess.F3, chess.F4, chess.F5, chess.F6}

KNIGHT_BONUS = {sq: (0.1 if sq in CENTER_SQUARES else 0.05 if sq in EXTENDED_CENTER else 0)
                for sq in chess.SQUARES}


def evaluate_board(board):
    """Positive = good for White, negative = good for Black. Used both by
    the fallback minimax and by the analysis feature."""
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        for sq in board.pieces(piece_type, chess.WHITE):
            score += piece_value(piece_type)
            if piece_type == chess.KNIGHT:
                score += KNIGHT_BONUS[sq]
        for sq in board.pieces(piece_type, chess.BLACK):
            score -= piece_value(piece_type)
            if piece_type == chess.KNIGHT:
                score -= KNIGHT_BONUS[sq]

    for square in CENTER_SQUARES:
        piece = board.piece_at(square)
        if piece:
            score += 0.3 if piece.color == chess.WHITE else -0.3
        if board.is_attacked_by(chess.WHITE, square):
            score += 0.1
        if board.is_attacked_by(chess.BLACK, square):
            score -= 0.1

    for color in (chess.WHITE, chess.BLACK):
        enemy = not color
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            for sq in board.pieces(piece_type, color):
                if board.is_attacked_by(enemy, sq) and not board.is_attacked_by(color, sq):
                    penalty = piece_value(piece_type) * 0.9
                    score += -penalty if color == chess.WHITE else penalty

    mover_mobility = board.legal_moves.count()
    score += 0.03 * mover_mobility * (1 if board.turn == chess.WHITE else -1)

    return score


def minimax(board, depth, alpha, beta, maximizing):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

    best_move = None
    legal_moves = list(board.legal_moves)

    if maximizing:
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move


def _fallback_ai_move(board, difficulty='medium'):
    """Pure-Python minimax used only if the Stockfish engine isn't
    available on this device/build."""
    legal_moves = list(board.legal_moves)
    if difficulty == 'easy':
        if random.random() < 0.35:
            return random.choice(legal_moves)
        _, best_move = minimax(board, 1, float('-inf'), float('inf'), board.turn == chess.WHITE)
        return best_move or random.choice(legal_moves)

    _, best_move = minimax(board, 2, float('-inf'), float('inf'), board.turn == chess.WHITE)
    return best_move or random.choice(legal_moves)


# ============================================
# Stockfish engine integration
# ============================================
# Stockfish gives genuinely strong play (unlike the hand-written
# evaluation above). We try to launch it via python-chess's UCI
# support; if the binary is missing or won't run on this device,
# every call transparently falls back to the Python minimax above,
# so the app never crashes because of this.

STOCKFISH_PATH = 'assets/stockfish'
_stockfish_engine = None
_stockfish_failed = False


def get_stockfish_engine():
    global _stockfish_engine, _stockfish_failed
    if _stockfish_failed:
        return None
    if _stockfish_engine is not None:
        return _stockfish_engine
    try:
        import os
        import stat
        if os.path.exists(STOCKFISH_PATH):
            try:
                st = os.stat(STOCKFISH_PATH)
                os.chmod(STOCKFISH_PATH, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            except Exception:
                pass
            _stockfish_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            return _stockfish_engine
    except Exception:
        pass
    _stockfish_failed = True
    return None


# Difficulty -> (Stockfish skill level 0-20, thinking time in seconds)
DIFFICULTY_SETTINGS = {
    'easy': (3, 0.3),
    'medium': (10, 0.6),
    'hard': (20, 1.2),
}


def ai_choose_move(board, difficulty='medium'):
    engine = get_stockfish_engine()
    if engine is not None:
        try:
            skill, think_time = DIFFICULTY_SETTINGS.get(difficulty, (10, 0.6))
            engine.configure({"Skill Level": skill})
            result = engine.play(board, chess.engine.Limit(time=think_time))
            if result.move is not None:
                return result.move
        except Exception:
            global _stockfish_failed
            _stockfish_failed = True

    return _fallback_ai_move(board, difficulty)


PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

LUNA_GREETINGS = [
    "Hey there! I'm Luna. Tap a piece, then tap where you want it to go.",
    "Hi, I'm Luna! Ready when you are — tap a piece to start.",
    "Welcome back! Let's see what you've got today.",
]

LUNA_GOOD_MOVE = [
    "Nice move!",
    "I like that.",
    "Solid choice.",
    "Hmm, interesting — let's see how this goes.",
    "That opens things up nicely.",
    "Okay, I wasn't expecting that one.",
    "Good, you're building something there.",
]

LUNA_USER_CAPTURE = [
    "Ooh, nice capture!",
    "You got one! Well played.",
    "That's a solid trade.",
    "Straight to the point, I like it.",
]

LUNA_AI_CAPTURE = [
    "Got one!",
    "Sorry about that one.",
    "Didn't see that coming, did you?",
    "That one was sitting there, honestly.",
]

LUNA_CHECK = [
    "Careful — check!",
    "Check! Better deal with that.",
    "Your king's exposed, watch out.",
]

LUNA_INVALID_MOVE = [
    "Hmm, that one's not legal.",
    "Can't go there, try again.",
    "Nope, that square's off-limits for that piece.",
]

LUNA_OPENING_COMMENTS = {
    "e2e4": "Classic. Fighting for the center right away.",
    "d2d4": "Queen's pawn — solid and flexible.",
    "g1f3": "Developing the knight early, I like it.",
    "c2c4": "The English — sneaky flank pressure.",
}

LUNA_TIPS = [
    "Try to hold the center if you can.",
    "Don't forget about castling — your king will thank you.",
    "Get your pieces out before you go on the attack.",
    "Keep an eye on what I might be threatening.",
    "No rush — take your time with this one.",
    "I wouldn't bring the queen out too early if I were you.",
    "Your pawns are the backbone here, watch how they line up.",
    "Open files are great for rooks, just saying.",
]

LUNA_GAME_OVER_DRAW = [
    "A draw! Honestly, a fair result.",
    "We're evenly matched — good game.",
]

LUNA_GAME_OVER_WIN = [
    "Wow, you got me. Well played!",
    "Checkmate — nicely done, seriously.",
    "Okay, that was a great game on your part.",
]

LUNA_GAME_OVER_LOSS = [
    "Got you this time! Good game though.",
    "That one's mine — you played well still.",
]


class Square(Button):
    def __init__(self, square_index, **kwargs):
        super().__init__(**kwargs)
        self.square_index = square_index
        self.font_size = 46
        if CHESS_FONT_NAME:
            self.font_name = CHESS_FONT_NAME
        self.background_normal = ''


class ChessBoard(GridLayout):
    def __init__(self, luna_panel, difficulty='medium', on_game_over=None, **kwargs):
        super().__init__(cols=8, rows=8, **kwargs)
        self.board = chess.Board()
        self.selected_square = None
        self.luna_panel = luna_panel
        self.squares = {}
        self.move_count = 0
        self.difficulty = difficulty
        self.sound_enabled = True
        self.voice_enabled = True
        self.on_game_over = on_game_over
        self.build_board()
        self.refresh_board()
        self.say(random.choice(LUNA_GREETINGS))

        # Load sound effects (app should still work if these fail to load)
        try:
            self.sound_move = SoundLoader.load('assets/move.wav')
            self.sound_capture = SoundLoader.load('assets/capture.wav')
            self.sound_check = SoundLoader.load('assets/check.wav')
        except Exception:
            self.sound_move = None
            self.sound_capture = None
            self.sound_check = None

    def play_sound(self, sound):
        if sound and self.sound_enabled:
            sound.stop()
            sound.play()

    def _animate_landing(self, square_index):
        """Briefly flash the destination square so a move feels like it
        landed, instead of pieces just silently swapping positions."""
        btn = self.squares.get(square_index)
        if not btn:
            return
        original_color = tuple(btn.background_color)
        flash_color = (1, 1, 1, 0.9)
        btn.background_color = flash_color
        anim = Animation(background_color=original_color, duration=0.25)
        anim.start(btn)

    def build_board(self):
        for rank in range(7, -1, -1):
            for file in range(8):
                idx = chess.square(file, rank)
                is_light = (file + rank) % 2 == 1
                color = LIGHT_SQUARE if is_light else DARK_SQUARE
                btn = Square(square_index=idx, background_color=color)
                btn.bind(on_release=self.on_square_press)
                self.squares[idx] = btn
                self.add_widget(btn)

    def refresh_board(self):
        legal_targets = set()
        if self.selected_square is not None:
            for m in self.board.legal_moves:
                if m.from_square == self.selected_square:
                    legal_targets.add(m.to_square)

        for idx, btn in self.squares.items():
            piece = self.board.piece_at(idx)
            btn.text = PIECE_SYMBOLS[piece.symbol()] if piece else ''

            file = chess.square_file(idx)
            rank = chess.square_rank(idx)
            is_light = (file + rank) % 2 == 1
            base_color = LIGHT_SQUARE if is_light else DARK_SQUARE

            if idx == self.selected_square:
                btn.background_color = SELECTED_SQUARE
            elif idx in legal_targets:
                btn.background_color = TARGET_SQUARE
            else:
                btn.background_color = base_color

            if piece is not None:
                if piece.color == chess.WHITE:
                    btn.color = (1, 1, 1, 1)
                    btn.outline_color = (0, 0, 0, 1)
                else:
                    btn.color = (0.05, 0.05, 0.08, 1)
                    btn.outline_color = (1, 1, 1, 1)
                btn.outline_width = 2

    def say(self, text):
        self.luna_panel.set_text("Luna: " + text)
        if TTS_AVAILABLE and self.voice_enabled:
            # Speak in a background thread so the UI never waits on the
            # text-to-speech engine (which can take a moment to start).
            def _speak():
                try:
                    tts.speak(message=text)
                except Exception:
                    pass
            threading.Thread(target=_speak, daemon=True).start()

    def on_square_press(self, instance):
        idx = instance.square_index

        if self.selected_square is None:
            piece = self.board.piece_at(idx)
            if piece and piece.color == chess.WHITE:
                self.selected_square = idx
                self.refresh_board()
            return

        move = chess.Move(self.selected_square, idx)

        # If this is a pawn promotion, ask the player which piece they want
        queen_promo = chess.Move(self.selected_square, idx, promotion=chess.QUEEN)
        if move not in self.board.legal_moves and queen_promo in self.board.legal_moves:
            self._ask_promotion(self.selected_square, idx)
            return

        if move in self.board.legal_moves:
            self.make_user_move(move)
        else:
            piece = self.board.piece_at(idx)
            if piece and piece.color == chess.WHITE:
                self.selected_square = idx
            else:
                self.selected_square = None
                self.luna_panel.set_mood('worried', duration=2)
                self.say(random.choice(LUNA_INVALID_MOVE))
        self.refresh_board()

    def _ask_promotion(self, from_square, to_square):
        content = BoxLayout(orientation='horizontal', spacing=8, padding=8)
        popup = Popup(
            title="Promote pawn to:",
            content=content,
            size_hint=(0.85, 0.25),
            auto_dismiss=False,
        )

        choices = [
            (chess.QUEEN, PIECE_SYMBOLS['Q']),
            (chess.ROOK, PIECE_SYMBOLS['R']),
            (chess.BISHOP, PIECE_SYMBOLS['B']),
            (chess.KNIGHT, PIECE_SYMBOLS['N']),
        ]

        def choose(piece_type):
            popup.dismiss()
            move = chess.Move(from_square, to_square, promotion=piece_type)
            if move in self.board.legal_moves:
                self.make_user_move(move)
            self.selected_square = None
            self.refresh_board()

        for piece_type, symbol in choices:
            btn = Button(text=symbol, font_size=36)
            if CHESS_FONT_NAME:
                btn.font_name = CHESS_FONT_NAME
            btn.bind(on_release=lambda inst, pt=piece_type: choose(pt))
            content.add_widget(btn)

        popup.open()

    def make_user_move(self, move):
        was_capture = self.board.is_capture(move)
        moved_piece = self.board.piece_at(move.from_square)
        piece_name = PIECE_NAMES.get(moved_piece.piece_type, "piece") if moved_piece else "piece"
        uci = move.uci()
        to_square = move.to_square

        self.board.push(move)
        self.selected_square = None
        self.refresh_board()
        self.move_count += 1
        self._animate_landing(to_square)

        self.play_sound(self.sound_capture if was_capture else self.sound_move)

        if self.board.is_game_over():
            self.announce_game_over()
            return

        # Special comment for well-known opening moves
        if self.move_count <= 2 and uci in LUNA_OPENING_COMMENTS:
            self.say(LUNA_OPENING_COMMENTS[uci])
        elif was_capture:
            self.luna_panel.set_mood('happy', duration=2)
            self.say(random.choice(LUNA_USER_CAPTURE))
        else:
            self.say(f"You moved your {piece_name}. " + random.choice(LUNA_GOOD_MOVE))

        # Luna "thinks" briefly before responding — scheduling this on the
        # next frame (rather than running it inline) keeps the tap feeling
        # instant instead of freezing while the AI calculates.
        self.luna_panel.set_mood('thinking')
        Clock.schedule_once(lambda dt: self._make_ai_move(), 0.35)

    def _make_ai_move(self):
        if self.board.is_game_over():
            return

        ai_move = ai_choose_move(self.board, self.difficulty)
        ai_capture = self.board.is_capture(ai_move)
        ai_piece = self.board.piece_at(ai_move.from_square)
        ai_piece_name = PIECE_NAMES.get(ai_piece.piece_type, "piece") if ai_piece else "piece"

        self.board.push(ai_move)
        self.refresh_board()
        self._animate_landing(ai_move.to_square)

        if self.board.is_check():
            self.play_sound(self.sound_check)
        else:
            self.play_sound(self.sound_capture if ai_capture else self.sound_move)

        if self.board.is_game_over():
            self.announce_game_over()
            return

        if self.board.is_check():
            self.luna_panel.set_mood('worried', duration=2)
            self.say(random.choice(LUNA_CHECK))
        elif ai_capture:
            self.luna_panel.set_mood('happy', duration=2)
            self.say(f"I captured with my {ai_piece_name}! " + random.choice(LUNA_AI_CAPTURE))
        else:
            self.luna_panel.set_mood('normal')
            self.say(random.choice(LUNA_TIPS))

    def announce_game_over(self):
        outcome = self.board.outcome()
        if outcome.winner is None:
            self.luna_panel.set_mood('normal')
            self.say(random.choice(LUNA_GAME_OVER_DRAW))
        elif outcome.winner == chess.WHITE:
            self.luna_panel.set_mood('happy')
            self.say(random.choice(LUNA_GAME_OVER_WIN))
        else:
            self.luna_panel.set_mood('worried')
            self.say(random.choice(LUNA_GAME_OVER_LOSS))

        if self.on_game_over:
            self.on_game_over()

    def analyze_game(self):
        """Walk back through the player's (White's) moves and flag the
        ones that lost the most material/position compared to what the
        engine considers the best alternative at that point. Each flagged
        move includes the FEN position right before it was played, so the
        board can be shown at that exact point."""
        moves_played = list(self.board.move_stack)
        replay = chess.Board()
        flagged = []

        for i, move in enumerate(moves_played):
            if replay.turn == chess.WHITE:
                position_before = replay.fen()
                # What Luna's engine would have played here
                best_move = ai_choose_move(replay, difficulty='hard')
                if best_move is not None and best_move != move:
                    replay.push(move)
                    score_played = evaluate_board(replay)
                    replay.pop()

                    replay.push(best_move)
                    score_best = evaluate_board(replay)
                    replay.pop()

                    if score_best - score_played >= 1.5:
                        move_number = (i // 2) + 1
                        flagged.append({
                            'move_number': move_number,
                            'played': replay.san(move),
                            'better': replay.san(best_move),
                            'fen_before': position_before,
                            'played_uci': move.uci(),
                            'better_uci': best_move.uci(),
                        })
            replay.push(move)

        return flagged

    def undo_move(self):
        """Undo the last full turn (Luna's move + the player's move before
        it), so it's always the player's turn again after undoing."""
        if len(self.board.move_stack) >= 2:
            self.board.pop()
            self.board.pop()
            self.selected_square = None
            self.refresh_board()
            self.luna_panel.set_mood('normal')
            self.say("Okay, let's take that back.")
        elif len(self.board.move_stack) == 1:
            self.board.pop()
            self.selected_square = None
            self.refresh_board()
            self.say("Back to the start of this turn.")
        else:
            self.say("Nothing to undo yet!")

    def give_hint(self):
        """Suggest a reasonable move for the player (White) using the same
        logic as the 'hard' AI, so the hint is genuinely useful."""
        if self.board.turn != chess.WHITE or self.board.is_game_over():
            return
        suggested = ai_choose_move(self.board, difficulty='hard')
        from_sq = chess.square_name(suggested.from_square)
        to_sq = chess.square_name(suggested.to_square)
        piece = self.board.piece_at(suggested.from_square)
        piece_name = PIECE_NAMES.get(piece.piece_type, "piece") if piece else "piece"
        self.luna_panel.set_mood('thinking', duration=2)
        self.say(f"Try moving your {piece_name} from {from_sq} to {to_sq}.")


class LunaPanel(BoxLayout):
    """Top panel with Luna's avatar and speech bubble"""

    AVATAR_SOURCES = {
        'normal': 'assets/luna_avatar.png',
        'happy': 'assets/luna_happy.png',
        'worried': 'assets/luna_worried.png',
        'thinking': 'assets/luna_thinking.png',
        'blink': 'assets/luna_normal_blink.png',
    }

    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', spacing=10, padding=10, **kwargs)
        with self.canvas.before:
            Color(*PANEL_COLOR)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.current_mood = 'normal'
        self._blink_scheduled = None
        self._mood_revert_scheduled = None

        self.avatar = Image(
            source=self.AVATAR_SOURCES['normal'],
            size_hint=(0.22, 1),
            allow_stretch=True,
            keep_ratio=True,
        )

        self.speech_label = Label(
            text="Luna: Hi!",
            size_hint=(0.78, 1),
            font_size=17,
            halign='left',
            valign='middle',
            color=(0.92, 0.94, 0.98, 1),
        )
        self.speech_label.bind(size=self._update_text_size)

        self.add_widget(self.avatar)
        self.add_widget(self.speech_label)

        # Start the idle blinking loop
        self._schedule_next_blink()
        # Gentle "breathing" pulse so the avatar feels alive even when
        # nothing else is happening — no image swapping needed.
        self._start_breathing()

    def _start_breathing(self):
        # Gentle opacity pulse so the avatar feels alive even when idle,
        # without swapping images or needing a custom property.
        breathing = (
            Animation(opacity=0.8, duration=1.6, t='in_out_sine')
            + Animation(opacity=1.0, duration=1.6, t='in_out_sine')
        )
        breathing.repeat = True
        breathing.start(self.avatar)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _update_text_size(self, instance, value):
        instance.text_size = (instance.width - 10, None)

    def set_text(self, text):
        self.speech_label.text = text
        # Small pop animation so new lines feel like they're being "said"
        anim = (
            Animation(font_size=self.speech_label.font_size + 3, duration=0.08)
            + Animation(font_size=17, duration=0.12)
        )
        anim.start(self.speech_label)

    def set_mood(self, mood, duration=None):
        """Switch avatar to a mood ('happy', 'worried', 'thinking', 'normal').
        If duration is given, automatically reverts to 'normal' after that
        many seconds."""
        if mood not in self.AVATAR_SOURCES:
            mood = 'normal'
        self.current_mood = mood
        self.avatar.source = self.AVATAR_SOURCES[mood]

        if self._mood_revert_scheduled:
            self._mood_revert_scheduled.cancel()
            self._mood_revert_scheduled = None

        if duration:
            self._mood_revert_scheduled = Clock.schedule_once(
                lambda dt: self.set_mood('normal'), duration
            )

    def _schedule_next_blink(self):
        wait = random.uniform(2.5, 5.5)
        self._blink_scheduled = Clock.schedule_once(self._do_blink, wait)

    def _do_blink(self, dt):
        # Only blink while in the normal mood, so it doesn't override
        # happy/worried/thinking expressions
        if self.current_mood == 'normal':
            self.avatar.source = self.AVATAR_SOURCES['blink']
            Clock.schedule_once(self._end_blink, 0.15)
        self._schedule_next_blink()

    def _end_blink(self, dt):
        if self.current_mood == 'normal':
            self.avatar.source = self.AVATAR_SOURCES['normal']


class MiniBoard(GridLayout):
    """A small, non-interactive board used in the analysis popup to show
    a position, the move that was played (red arrow-ish highlight on the
    destination square), and the engine's suggested move (green)."""

    def __init__(self, fen, highlight_uci=None, better_uci=None, **kwargs):
        super().__init__(cols=8, rows=8, **kwargs)
        board = chess.Board(fen)

        played_from = played_to = None
        if highlight_uci:
            played_from = chess.parse_square(highlight_uci[0:2])
            played_to = chess.parse_square(highlight_uci[2:4])

        better_from = better_to = None
        if better_uci:
            better_from = chess.parse_square(better_uci[0:2])
            better_to = chess.parse_square(better_uci[2:4])

        for rank in range(7, -1, -1):
            for file in range(8):
                idx = chess.square(file, rank)
                is_light = (file + rank) % 2 == 1
                color = LIGHT_SQUARE if is_light else DARK_SQUARE

                if idx in (played_from, played_to):
                    color = (0.75, 0.35, 0.35, 1)
                elif idx in (better_from, better_to):
                    color = (0.35, 0.65, 0.40, 1)

                piece = board.piece_at(idx)
                lbl = Label(
                    text=PIECE_SYMBOLS[piece.symbol()] if piece else '',
                    font_size=24,
                )
                if CHESS_FONT_NAME:
                    lbl.font_name = CHESS_FONT_NAME
                if piece is not None:
                    lbl.color = (1, 1, 1, 1) if piece.color == chess.WHITE else (0.05, 0.05, 0.08, 1)

                with lbl.canvas.before:
                    Color(*color)
                    rect = Rectangle(pos=lbl.pos, size=lbl.size)
                lbl.bind(
                    pos=lambda inst, val, r=rect: setattr(r, 'pos', val),
                    size=lambda inst, val, r=rect: setattr(r, 'size', val),
                )

                self.add_widget(lbl)


class ChessRoot(BoxLayout):
    def __init__(self, difficulty='medium', on_home=None, **kwargs):
        super().__init__(orientation='vertical', spacing=8, padding=8, **kwargs)
        with self.canvas.before:
            Color(*BG_COLOR)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.difficulty = difficulty
        self.on_home = on_home
        self.luna_panel = LunaPanel(size_hint=(1, 0.16))

        self.board_widget = ChessBoard(
            self.luna_panel, difficulty=self.difficulty,
            on_game_over=self._on_game_over, size_hint=(1, 0.64)
        )

        self._build_layout()

    def _on_game_over(self):
        self.analyze_btn.disabled = False
        self.analyze_btn.background_color = (0.55, 0.45, 0.85, 1)

    def toggle_sfx(self, instance):
        self.board_widget.sound_enabled = not self.board_widget.sound_enabled
        self.sfx_btn.text = "SFX: On" if self.board_widget.sound_enabled else "SFX: Off"

    def toggle_voice(self, instance):
        self.board_widget.voice_enabled = not self.board_widget.voice_enabled
        self.voice_btn.text = "Voice: On" if self.board_widget.voice_enabled else "Voice: Off"

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def restart(self, instance):
        self.clear_widgets()
        self.board_widget = ChessBoard(
            self.luna_panel, difficulty=self.difficulty,
            on_game_over=self._on_game_over, size_hint=(1, 0.64)
        )
        self._build_layout()
        self.analyze_btn.disabled = True
        self.analyze_btn.background_color = (0.3, 0.3, 0.35, 1)

    def _build_layout(self):
        button_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.10), spacing=6)

        undo_btn = Button(
            text="Undo",
            background_color=(0.29, 0.36, 0.46, 1),
            color=(1, 1, 1, 1),
        )
        undo_btn.bind(on_release=lambda inst: self.board_widget.undo_move())

        hint_btn = Button(
            text="Hint",
            background_color=(0.45, 0.40, 0.60, 1),
            color=(1, 1, 1, 1),
        )
        hint_btn.bind(on_release=lambda inst: self.board_widget.give_hint())

        restart_btn = Button(
            text="Restart",
            background_color=(0.29, 0.36, 0.46, 1),
            color=(1, 1, 1, 1),
        )
        restart_btn.bind(on_release=self.restart)

        home_btn = Button(
            text="< Menu",
            background_color=(0.35, 0.30, 0.45, 1),
            color=(1, 1, 1, 1),
        )
        home_btn.bind(on_release=lambda inst: self.on_home() if self.on_home else None)

        button_row.add_widget(undo_btn)
        button_row.add_widget(hint_btn)
        button_row.add_widget(restart_btn)
        button_row.add_widget(home_btn)

        second_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.09), spacing=6)

        self.sfx_btn = Button(
            text="SFX: On" if self.board_widget.sound_enabled else "SFX: Off",
            background_color=(0.29, 0.36, 0.46, 1),
            color=(1, 1, 1, 1),
        )
        self.sfx_btn.bind(on_release=self.toggle_sfx)

        self.voice_btn = Button(
            text="Voice: On" if self.board_widget.voice_enabled else "Voice: Off",
            background_color=(0.29, 0.36, 0.46, 1),
            color=(1, 1, 1, 1),
        )
        self.voice_btn.bind(on_release=self.toggle_voice)

        self.analyze_btn = Button(
            text="Analyze",
            background_color=(0.3, 0.3, 0.35, 1),
            color=(0.7, 0.7, 0.7, 1),
            disabled=True,
        )
        self.analyze_btn.bind(on_release=self.show_analysis)

        second_row.add_widget(self.sfx_btn)
        second_row.add_widget(self.voice_btn)
        second_row.add_widget(self.analyze_btn)

        self.add_widget(self.luna_panel)
        self.add_widget(self.board_widget)
        self.add_widget(button_row)
        self.add_widget(second_row)

    def show_analysis(self, instance):
        flagged = self.board_widget.analyze_game()

        if not flagged:
            popup = Popup(
                title="Game Analysis",
                content=Label(
                    text="Nice game! I didn't spot any moves that\nclearly lost material or position.",
                    color=(0.92, 0.94, 0.98, 1),
                    halign='center',
                ),
                size_hint=(0.85, 0.3),
            )
            popup.open()
            return

        self._analysis_index = 0
        self._analysis_flagged = flagged
        self._open_analysis_popup()

    def _open_analysis_popup(self):
        flagged = self._analysis_flagged
        idx = self._analysis_index
        item = flagged[idx]

        outer = BoxLayout(orientation='vertical', spacing=8, padding=8)

        header = Label(
            text=f"Move {item['move_number']} of {len(flagged)} flagged\n"
                 f"You played: {item['played']}   —   Better: {item['better']}",
            size_hint=(1, 0.2),
            color=(0.92, 0.94, 0.98, 1),
            halign='center',
        )
        header.bind(size=lambda inst, s: setattr(inst, 'text_size', s))

        mini_board = MiniBoard(
            fen=item['fen_before'],
            highlight_uci=item['played_uci'],
            better_uci=item['better_uci'],
            size_hint=(1, 0.6),
        )

        nav_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.12), spacing=6)
        prev_btn = Button(text="< Prev", disabled=(idx == 0))
        next_btn = Button(text="Next >", disabled=(idx == len(flagged) - 1))
        nav_row.add_widget(prev_btn)
        nav_row.add_widget(next_btn)

        close_btn = Button(text="Close", size_hint=(1, 0.12))

        outer.add_widget(header)
        outer.add_widget(mini_board)
        outer.add_widget(nav_row)
        outer.add_widget(close_btn)

        popup = Popup(title="Game Analysis", content=outer, size_hint=(0.92, 0.85))

        def go_prev(inst):
            popup.dismiss()
            self._analysis_index -= 1
            self._open_analysis_popup()

        def go_next(inst):
            popup.dismiss()
            self._analysis_index += 1
            self._open_analysis_popup()

        prev_btn.bind(on_release=go_prev)
        next_btn.bind(on_release=go_next)
        close_btn.bind(on_release=popup.dismiss)

        popup.open()


class StartScreen(BoxLayout):
    """Shown before the board: pick a difficulty, then start the game."""

    def __init__(self, on_start, **kwargs):
        super().__init__(orientation='vertical', spacing=16, padding=32, **kwargs)
        self.on_start = on_start
        self.selected_difficulty = 'medium'

        with self.canvas.before:
            Color(*BG_COLOR)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        title = Label(
            text="Luna Chess",
            font_size=32,
            bold=True,
            color=(0.92, 0.94, 0.98, 1),
            size_hint=(1, 0.15),
        )

        avatar = Image(
            source='assets/luna_avatar.png',
            size_hint=(1, 0.35),
            allow_stretch=True,
            keep_ratio=True,
        )

        subtitle = Label(
            text="Choose a difficulty to begin",
            font_size=16,
            color=(0.75, 0.78, 0.85, 1),
            size_hint=(1, 0.08),
        )

        self.buttons = {}
        options_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.15), spacing=8)
        for level, label in [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]:
            btn = Button(
                text=label,
                background_color=(0.45, 0.70, 0.55, 1) if level == 'medium'
                else (0.29, 0.36, 0.46, 1),
                color=(1, 1, 1, 1),
            )
            btn.bind(on_release=lambda inst, lvl=level: self._select_difficulty(lvl))
            self.buttons[level] = btn
            options_row.add_widget(btn)

        start_btn = Button(
            text="Start Game",
            size_hint=(1, 0.15),
            background_color=(0.55, 0.45, 0.85, 1),
            color=(1, 1, 1, 1),
            font_size=18,
        )
        start_btn.bind(on_release=lambda inst: self.on_start(self.selected_difficulty))

        self.add_widget(title)
        self.add_widget(avatar)
        self.add_widget(subtitle)
        self.add_widget(options_row)
        self.add_widget(start_btn)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _select_difficulty(self, level):
        self.selected_difficulty = level
        for lvl, btn in self.buttons.items():
            btn.background_color = (
                (0.45, 0.70, 0.55, 1) if lvl == level else (0.29, 0.36, 0.46, 1)
            )


class LunaChessApp(App):
    def build(self):
        Window.clearcolor = BG_COLOR
        self.root_layout = BoxLayout()
        self.show_start_screen(animate=False)
        return self.root_layout

    def _switch_screen(self, new_widget, animate=True):
        """Fade out the current screen, swap it, then fade the new one in,
        so screen changes feel like a transition instead of an instant cut."""
        if not animate or not self.root_layout.children:
            self.root_layout.clear_widgets()
            new_widget.opacity = 1
            self.root_layout.add_widget(new_widget)
            return

        old_widget = self.root_layout.children[0]

        def _swap(dt):
            self.root_layout.clear_widgets()
            new_widget.opacity = 0
            self.root_layout.add_widget(new_widget)
            Animation(opacity=1, duration=0.18, t='out_quad').start(new_widget)

        Animation(opacity=0, duration=0.15, t='in_quad').start(old_widget)
        Clock.schedule_once(_swap, 0.15)

    def show_start_screen(self, animate=True):
        self._switch_screen(StartScreen(on_start=self.start_game), animate=animate)

    def start_game(self, difficulty):
        self._switch_screen(
            ChessRoot(difficulty=difficulty, on_home=self.show_start_screen)
        )


if __name__ == '__main__':
    LunaChessApp().run()
