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


def ai_choose_move(board):
    legal_moves = list(board.legal_moves)
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
    "Hi! I'm Luna. Tap a square, then tap where you'd like to move.",
    "Welcome! I'm Luna, and I'll keep you company in this game. Shall we begin?",
]

LUNA_GOOD_MOVE = [
    "Nice move!",
    "I think that was the right call.",
    "Well played.",
    "Great, keep that up!",
    "That move gives you good control of the board.",
]

LUNA_USER_CAPTURE = [
    "You captured a piece! Nicely done.",
    "Great strike! Your opponent just lost a piece.",
    "That was a profitable exchange.",
]

LUNA_AI_CAPTURE = [
    "I captured a piece, watch out!",
    "That move cost you a piece, I think.",
    "Hmm, that worked out well for me.",
]

LUNA_CHECK = [
    "Careful, your king is in check!",
    "Watch out — check! Protect your king.",
    "This is serious, the king is under threat!",
]

LUNA_INVALID_MOVE = [
    "That move isn't allowed, try again.",
    "Sorry, you can't move there.",
    "Try selecting a different square.",
]

LUNA_OPENING_COMMENTS = {
    "e2e4": "A classic opening! You're fighting for the center.",
    "d2d4": "Starting with the queen's pawn — a solid choice.",
    "g1f3": "Developing the knight early isn't a bad idea.",
    "c2c4": "The English Opening — pressure from the flank.",
}

LUNA_TIPS = [
    "Try to control the center of the board.",
    "Protect your king early — think about castling.",
    "Develop your pieces, don't leave them stuck in one place.",
    "Always watch for your opponent's threats.",
    "Think twice before every move!",
    "Avoid bringing your queen out too early.",
    "Your pawn structure will affect the rest of the game.",
    "Rooks and queens are stronger on open files.",
]

LUNA_GAME_OVER_DRAW = [
    "The game ended in a draw. Good fight!",
    "A draw! We both played well.",
]

LUNA_GAME_OVER_WIN = [
    "Congratulations, you won!",
    "Great game, you checkmated me!",
    "That was a fantastic strategy, well deserved win!",
]

LUNA_GAME_OVER_LOSS = [
    "I won this time, better luck next time!",
    "Good fight, but I won this round.",
]


class Square(Button):
    def __init__(self, square_index, **kwargs):
        super().__init__(**kwargs)
        self.square_index = square_index
        self.font_size = 32
        if CHESS_FONT_NAME:
            self.font_name = CHESS_FONT_NAME
        self.background_normal = ''


class ChessBoard(GridLayout):
    def __init__(self, luna_panel, **kwargs):
        super().__init__(cols=8, rows=8, **kwargs)
        self.board = chess.Board()
        self.selected_square = None
        self.luna_panel = luna_panel
        self.squares = {}
        self.move_count = 0
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
        if sound:
            sound.stop()
            sound.play()

    def build_board(self):
        for rank in range(7, -1, -1):
            for file in range(8):
                idx = chess.square(file, rank)
                is_light = (file + rank) % 2 == 1
                color = LIGHT_SQUARE if is_light else DARK_SQUARE
                btn = Square(square_index=idx, background_color=color)
                btn.color = (0.95, 0.97, 1, 1) if not is_light else (0.15, 0.2, 0.3, 1)
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

    def say(self, text):
        self.luna_panel.set_text("Luna: " + text)
        if TTS_AVAILABLE:
            try:
                tts.speak(message=text)
            except Exception:
                pass

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

        self.board.push(move)
        self.selected_square = None
        self.refresh_board()
        self.move_count += 1

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
        ai_move = ai_choose_move(self.board)
        ai_capture = self.board.is_capture(ai_move)
        ai_piece = self.board.piece_at(ai_move.from_square)
        ai_piece_name = PIECE_NAMES.get(ai_piece.piece_type, "piece") if ai_piece else "piece"

        self.board.push(ai_move)
        self.refresh_board()

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
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=8, padding=8, **kwargs)
        with self.canvas.before:
            Color(*BG_COLOR)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.luna_panel = LunaPanel(size_hint=(1, 0.16))

        self.board_widget = ChessBoard(self.luna_panel, size_hint=(1, 0.74))

        restart_btn = Button(
            text="Restart",
            size_hint=(1, 0.10),
            background_color=(0.29, 0.36, 0.46, 1),
            color=(1, 1, 1, 1),
        )
        restart_btn.bind(on_release=self.restart)

        self.add_widget(self.luna_panel)
        self.add_widget(self.board_widget)
        self.add_widget(restart_btn)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def restart(self, instance):
        self.remove_widget(self.board_widget)
        self.board_widget = ChessBoard(self.luna_panel, size_hint=(1, 0.74))
        self.add_widget(self.board_widget, index=1)


class LunaChessApp(App):
    def build(self):
        Window.clearcolor = BG_COLOR
        return ChessRoot()


if __name__ == '__main__':
    LunaChessApp().run()
