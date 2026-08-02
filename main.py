import chess
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


def ai_choose_move(board, difficulty='medium'):
    """difficulty: 'easy' (mostly random), 'medium' (captures + checks),
    'hard' (captures + checks + avoids losing material for free)."""
    legal_moves = list(board.legal_moves)

    if difficulty == 'easy':
        # Occasionally still grab a free capture, but mostly plays randomly
        if random.random() < 0.3:
            for move in legal_moves:
                if board.is_capture(move):
                    return move
        return random.choice(legal_moves)

    best_capture = None
    best_value = -1
    for move in legal_moves:
        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
            if captured_piece:
                value = piece_value(captured_piece.piece_type)
                if value > best_value:
                    best_value = value
                    best_capture = move

    if difficulty == 'hard':
        # Prefer captures that don't immediately lose more value than they
        # gain (simple 1-ply safety check).
        safe_moves = []
        for move in legal_moves:
            board.push(move)
            attacked = board.is_attacked_by(not board.turn, move.to_square)
            board.pop()
            if not attacked:
                safe_moves.append(move)

        if best_capture and best_capture in safe_moves:
            return best_capture

        for move in legal_moves:
            board.push(move)
            gives_check = board.is_check()
            board.pop()
            if gives_check and move in safe_moves:
                return move

        if safe_moves:
            return random.choice(safe_moves)

    if best_capture:
        return best_capture

    for move in legal_moves:
        board.push(move)
        if board.is_check():
            board.pop()
            return move
        board.pop()
    return random.choice(legal_moves)


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
    def __init__(self, luna_panel, difficulty='medium', **kwargs):
        super().__init__(cols=8, rows=8, **kwargs)
        self.board = chess.Board()
        self.selected_square = None
        self.luna_panel = luna_panel
        self.squares = {}
        self.move_count = 0
        self.difficulty = difficulty
        self.sound_enabled = True
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
        if TTS_AVAILABLE:
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

        # Auto-promote pawns reaching the last rank to a queen
        if move not in self.board.legal_moves:
            promo_move = chess.Move(self.selected_square, idx, promotion=chess.QUEEN)
            if promo_move in self.board.legal_moves:
                move = promo_move

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

        # Luna "thinks" briefly before responding
        self.luna_panel.set_mood('thinking')

        # Luna's (Black's) response
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
            self.luna_panel, difficulty=self.difficulty, size_hint=(1, 0.64)
        )

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

        button_row.add_widget(undo_btn)
        button_row.add_widget(hint_btn)
        button_row.add_widget(restart_btn)

        second_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.09), spacing=6)

        home_btn = Button(
            text="< Menu",
            background_color=(0.35, 0.30, 0.45, 1),
            color=(1, 1, 1, 1),
        )
        home_btn.bind(on_release=lambda inst: self.on_home() if self.on_home else None)

        self.sound_btn = Button(
            text="Sound: On",
            background_color=(0.29, 0.36, 0.46, 1),
            color=(1, 1, 1, 1),
        )
        self.sound_btn.bind(on_release=self.toggle_sound)

        second_row.add_widget(home_btn)
        second_row.add_widget(self.sound_btn)

        self.add_widget(self.luna_panel)
        self.add_widget(self.board_widget)
        self.add_widget(button_row)
        self.add_widget(second_row)

    def toggle_sound(self, instance):
        self.board_widget.sound_enabled = not self.board_widget.sound_enabled
        self.sound_btn.text = "Sound: On" if self.board_widget.sound_enabled else "Sound: Off"

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def restart(self, instance):
        self.remove_widget(self.board_widget)
        self.board_widget = ChessBoard(
            self.luna_panel, difficulty=self.difficulty, size_hint=(1, 0.64)
        )
        self.add_widget(self.board_widget, index=1)


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
        self.show_start_screen()
        return self.root_layout

    def show_start_screen(self):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(StartScreen(on_start=self.start_game))

    def start_game(self, difficulty):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(
            ChessRoot(difficulty=difficulty, on_home=self.show_start_screen)
        )


if __name__ == '__main__':
    LunaChessApp().run()
