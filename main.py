import threading
import requests
import chess

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.properties import StringProperty

# Donalarning Yunikod belgilari (Rasm shart emas)
PIECE_SYMBOLS = {
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
    'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
}

KV = '''
<ChessGameWidget>:
    orientation: 'vertical'

    # Yuqori panel: Baholash bar va Best Move
    BoxLayout:
        size_hint_y: 0.12
        orientation: 'vertical'
        padding: 5
        canvas.before:
            Color:
                rgba: 0.1, 0.1, 0.1, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: root.eval_status
            font_size: '18sp'
            bold: True
            color: (0.3, 0.9, 0.3, 1)

        Label:
            text: "Eng yaxshi yurish: " + root.best_move_text
            font_size: '15sp'
            color: (0.9, 0.9, 0.9, 1)

    # Shaxmat taxtasi (8x8 Grid)
    GridLayout:
        id: board_grid
        cols: 8
        rows: 8
        size_hint_y: 0.73
        padding: 2
        spacing: 1

    # Boshqaruv tugmalari va PGN
    BoxLayout:
        size_hint_y: 0.15
        orientation: 'vertical'
        padding: 5
        spacing: 5

        Label:
            text: root.last_move_str
            size_hint_y: 0.4
            font_size: '14sp'
            color: (0.8, 0.8, 0.8, 1)

        BoxLayout:
            size_hint_y: 0.6
            spacing: 10

            Button:
                text: "Yangi O'yin"
                on_release: root.reset_game()

            Button:
                text: "Tahlil qilish"
                on_release: root.analyze_position()
'''

Builder.load_string(KV)


class ChessSquareButton(Button):
    def __init__(self, square_id, **kwargs):
        super().__init__(**kwargs)
        self.square_id = square_id  # 0-63 indeksi (chess.A1 ... chess.H8)
        self.font_name = 'DejaVuSans' if False else self.font_name  # Standart shrift
        self.font_size = '32sp'


class ChessGameWidget(BoxLayout):
    eval_status = StringProperty("Baho: +0.00")
    best_move_text = StringProperty("—")
    last_move_str = StringProperty("Yurish qilish uchun donani bosing.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.board = chess.Board()
        self.selected_square = None
        self.square_buttons = {}
        
        # Ekran tayyor bo'lgach taxtani chizish
        Clock.schedule_once(lambda dt: self.build_board_ui())

    def build_board_ui(self):
        """8x8 Shaxmat taxtasini tugmalar bilan to'ldirish"""
        grid = self.ids.board_grid
        grid.clear_widgets()

        # Shaxmatda 8-qatordan 1-qatorgacha chiziladi
        for rank in range(7, -1, -1):
            for file in range(8):
                sq_id = chess.square(file, rank)
                btn = ChessSquareButton(square_id=sq_id)
                
                # Katak ranglari (Oq / Qora)
                is_light = (rank + file) % 2 != 0
                btn.background_normal = ''
                btn.background_color = (0.93, 0.93, 0.82, 1) if is_light else (0.46, 0.58, 0.33, 1)
                
                btn.bind(on_release=self.on_square_click)
                grid.add_widget(btn)
                self.square_buttons[sq_id] = btn

        self.update_board_ui()

    def update_board_ui(self):
        """Taxtadagi donalarni joriy holat bo'yicha yangilash"""
        for sq_id, btn in self.square_buttons.items():
            piece = self.board.piece_at(sq_id)
            if piece:
                btn.text = PIECE_SYMBOLS.get(piece.symbol(), '')
                # Oq donalar sariq/oq, qoralar to'q rangda
                btn.color = (1, 1, 1, 1) if piece.color == chess.WHITE else (0, 0, 0, 1)
            else:
                btn.text = ''

            # Ranglarni dastalabki holatga qaytarish
            file = chess.square_file(sq_id)
            rank = chess.square_rank(sq_id)
            is_light = (rank + file) % 2 != 0
            btn.background_color = (0.93, 0.93, 0.82, 1) if is_light else (0.46, 0.58, 0.33, 1)

        # Tanlangan katakni belgilash
        if self.selected_square is not None:
            self.square_buttons[self.selected_square].background_color = (0.8, 0.8, 0.2, 1)

    def on_square_click(self, btn):
        """Katak bosilganda yurish qilish mantiqi"""
        clicked_sq = btn.square_id

        # 1. Birinchi marta dona tanlash
        if self.selected_square is None:
            piece = self.board.piece_at(clicked_sq)
            if piece and piece.color == self.board.turn:
                self.selected_square = clicked_sq
                self.update_board_ui()
        else:
            # 2. Tanlangan donani yangi katakka yurish
            move = chess.Move(self.selected_square, clicked_sq)
            
            # Piyoda oxiriga etganda Farzin aylanishi
            if chess.Move(self.selected_square, clicked_sq, promotion=chess.QUEEN) in self.board.legal_moves:
                move = chess.Move(self.selected_square, clicked_sq, promotion=chess.QUEEN)

            if move in self.board.legal_moves:
                san_move = self.board.san(move)
                self.board.push(move)
                self.last_move_str = f"Oxirgi yurish: {san_move}"
                self.selected_square = None
                self.update_board_ui()
                
                # Yurish qilingach, avtomatik tahlil chaqirish
                self.analyze_position()
            else:
                # Agar boshqa o'z donasini bossa, tanlovni o'zgartirish
                piece = self.board.piece_at(clicked_sq)
                if piece and piece.color == self.board.turn:
                    self.selected_square = clicked_sq
                else:
                    self.selected_square = None
                self.update_board_ui()

    def reset_game(self):
        """O'yinni boshiga qaytarish"""
        self.board.reset()
        self.selected_square = None
        self.eval_status = "Baho: +0.00"
        self.best_move_text = "—"
        self.last_move_str = "Yangi o'yin boshlandi."
        self.update_board_ui()

    def analyze_position(self):
        """Stockfish (Lichess Cloud API) orqali fon rejimidagi tahlil"""
        self.best_move_text = "Hisoblanmoqda..."
        fen = self.board.fen()

        def fetch():
            best_move = None
            score_str = "0.00"
            try:
                url = "https://lichess.org/api/cloud-eval"
                res = requests.get(url, params={"fen": fen}, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    pvs = data.get("pvs", [])
                    if pvs:
                        uci_move = pvs[0]["moves"].split()[0]
                        move_obj = chess.Move.from_uci(uci_move)
                        best_move = self.board.san(move_obj)

                        if "cp" in pvs[0]:
                            cp = pvs[0]["cp"] / 100.0
                            score_str = f"{cp:+.2f}"
                        elif "mate" in pvs[0]:
                            score_str = f"M{pvs[0]['mate']}"
            except Exception as e:
                print(f"API Error: {e}")

            Clock.schedule_once(lambda dt: self._apply_analysis(best_move, score_str))

        threading.Thread(target=fetch, daemon=True).start()

    def _apply_analysis(self, best_move, score_str):
        if best_move:
            self.best_move_text = str(best_move)
            self.eval_status = f"Baho: {score_str}"
        else:
            self.best_move_text = "Topilmadi"
            self.eval_status = "Baho: —"


class LunaChessApp(App):
    def build(self):
        self.title = "Luna Chess Pro"
        return ChessGameWidget()


if __name__ == "__main__":
    LunaChessApp().run()
      
