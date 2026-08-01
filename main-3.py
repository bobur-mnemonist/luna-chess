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

# ============================================
# Belgilar (unicode shaxmat figuralar)
# ============================================

PIECE_SYMBOLS = {
    'P': '\u2659', 'N': '\u2658', 'B': '\u2657',
    'R': '\u2656', 'Q': '\u2655', 'K': '\u2654',
    'p': '\u265F', 'n': '\u265E', 'b': '\u265D',
    'r': '\u265C', 'q': '\u265B', 'k': '\u265A',
}

# ============================================
# Ko'k-kulrang zamonaviy rang palitrasi
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


def ai_yurish_tanlash(board):
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


AIGUL_MASLAHATLAR = [
    "Markazni nazorat qilishga harakat qiling.",
    "Shohingizni erta himoya qiling.",
    "Figuralaringizni rivojlantiring.",
    "Raqibning tahdidlariga e'tibor bering.",
    "Har bir yurishdan oldin ikki marta o'ylang!",
]


class Square(Button):
    def __init__(self, square_index, **kwargs):
        super().__init__(**kwargs)
        self.square_index = square_index
        self.font_size = 32
        self.background_normal = ''


class ChessBoard(GridLayout):
    def __init__(self, luna_label, **kwargs):
        super().__init__(cols=8, rows=8, **kwargs)
        self.board = chess.Board()
        self.selected_square = None
        self.luna_label = luna_label
        self.squares = {}
        self.build_board()
        self.refresh_board()
        self.say("Salom! Men Lunaman. Bir katakni bosib, keyin qayerga "
                 "yurmoqchi ekaningizni bosing.")

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
        self.luna_label.set_text("Luna: " + text)

    def on_square_press(self, instance):
        idx = instance.square_index

        if self.selected_square is None:
            piece = self.board.piece_at(idx)
            if piece and piece.color == chess.WHITE:
                self.selected_square = idx
                self.refresh_board()
            return

        move = chess.Move(self.selected_square, idx)

        # Piyoda oxirgi qatorga yetsa, avtomatik farzinga aylantiramiz
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
                self.say("Bu yurish mumkin emas, qaytadan urinib ko'ring.")
        self.refresh_board()

    def make_user_move(self, move):
        was_capture = self.board.is_capture(move)
        self.board.push(move)
        self.selected_square = None
        self.refresh_board()

        if self.board.is_game_over():
            self.announce_game_over()
            return

        msg = "Yaxshi yurish!" if not was_capture else "Bir dona yeb qo'ydingiz!"
        self.say(msg)

        # Luna (Qora) javobi
        ai_move = ai_yurish_tanlash(self.board)
        ai_capture = self.board.is_capture(ai_move)
        self.board.push(ai_move)
        self.refresh_board()

        if self.board.is_game_over():
            self.announce_game_over()
            return

        if self.board.is_check():
            self.say("Diqqat, shohingiz shax ostida!")
        elif ai_capture:
            self.say("Men bir dona yedim! " + random.choice(AIGUL_MASLAHATLAR))
        else:
            self.say(random.choice(AIGUL_MASLAHATLAR))

    def announce_game_over(self):
        outcome = self.board.outcome()
        if outcome.winner is None:
            self.say("O'yin durang bilan tugadi. Yaxshi kurash edi!")
        elif outcome.winner == chess.WHITE:
            self.say("Tabriklayman, siz g'alaba qozondingiz!")
        else:
            self.say("Bu safar men g'alaba qozondim, keyingi safar omad tilayman!")


class LunaPanel(BoxLayout):
    """Luna avatari + gaplashuv pufakchasi joylashgan yuqori panel"""
    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', spacing=10, padding=10, **kwargs)
        with self.canvas.before:
            Color(*PANEL_COLOR)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Luna avatari - haqiqiy rasm
        self.avatar = Image(
            source='assets/luna_avatar.png',
            size_hint=(0.22, 1),
            allow_stretch=True,
            keep_ratio=True,
        )

        self.speech_label = Label(
            text="Luna: Salom!",
            size_hint=(0.78, 1),
            font_size=17,
            halign='left',
            valign='middle',
            color=(0.92, 0.94, 0.98, 1),
        )
        self.speech_label.bind(size=self._update_text_size)

        self.add_widget(self.avatar)
        self.add_widget(self.speech_label)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _update_text_size(self, instance, value):
        instance.text_size = (instance.width - 10, None)

    def set_text(self, text):
        self.speech_label.text = text


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
            text="Qaytadan boshlash",
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
