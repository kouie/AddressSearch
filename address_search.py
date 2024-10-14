import csv
import re
import os
from fuzzywuzzy import fuzz
import pyperclip
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QListWidget, QLabel, QSlider, QHBoxLayout, QComboBox, QPushButton
from PyQt5.QtCore import QTimer, Qt
import sys
from PyQt5.QtGui import QFont



class AddressSearcher:
    def __init__(self, csv_file):
        self.addresses = self.load_addresses(csv_file)

    def load_addresses(self, csv_file):
        addresses = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
#            next(reader)  # ヘッダーをスキップ
            for row in reader:
                postal_code = row[2]
                kana_address = ''.join(row[3:6])
                kanji_address = ' '.join(row[6:9])
                addresses.append((postal_code, kana_address, kanji_address))
        return addresses

    def search(self, query, threshold=70, top=20):
        switch = query[-1]
        if (switch == "f"):
            query = query[:-1]
            results = self.f_search(query, threshold) 

        elif (switch == "r"):
            query = query[:-1]
            results = []
            for postal_code, kana_address, kanji_address in self.addresses:
                normalized_kanji = self.normalize(kanji_address)
                result = re.search(query, normalized_kanji)
                if result:
                    results.append((f"{postal_code} {kanji_address}", 0))
        else:
            query = self.q_normalize(query)
            results = []
            queries = query.split(' ')
            for postal_code, kana_address, kanji_address in self.addresses:
                normalized_kanji = self.normalize(kanji_address)
                if all(w in normalized_kanji for w in queries):
                    results.append((f"{postal_code} {kanji_address}", 0))

        return results[:top]

    def f_search(self, query, threshold=70):
        query = self.normalize(query)
        if (',' in query):
            fix, query = query.split(',')
        else:
            fix = ''

        results = []
        for postal_code, kana_address, kanji_address in self.addresses:
#            normalized_kana = self.normalize(kana_address)
            
            if (fix != '' and fix not in kanji_address):
                continue
            if (len(query) > len(kanji_address)):
                continue
            
#            kana_ratio = fuzz.partial_ratio(query, normalized_kana)

            normalized_kanji = self.normalize(kanji_address)
            kanji_ratio = fuzz.partial_ratio(query, normalized_kanji)

#            max_ratio = max(kana_ratio, kanji_ratio)
            max_ratio = kanji_ratio
            
            if max_ratio != 100 and max_ratio > threshold:
                results.append((f"{postal_code} {kanji_address}", max_ratio))
        
        # ソート: 類似度の高い順
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def normalize(self, text):
        # 正規化処理
        text = text.replace('ヶ', 'ケ').replace('ヵ', 'カ')
        text = text.replace('の', 'ノ')
        text = text.replace('ッ', 'ツ')
        text = re.sub(r'\d+', lambda m: str(int(m.group())), text)
        text = re.sub(r'\s+', '', text)  # スペースを削除
        return text.lower()

    def q_normalize(self, text):
        # 正規化処理
        text = text.replace('ヶ', 'ケ').replace('ヵ', 'カ')
        text = text.replace('の', 'ノ')
        text = text.replace('ッ', 'ツ')
        text = text.replace('大字','')
        text = re.sub(r'\d+', lambda m: str(int(m.group())), text)
        return text.lower()


class AddressSearchApp(QWidget):
    def __init__(self, searcher):
        super().__init__()
        self.searcher = searcher
        self.last_clipboard = ""
        self.last_qword = ""
        self.threshold = 70
        self.top = 10
        self.fontsize = 14
        self.always_on_top = False
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        

        self.label = QLabel("検索文字列")
        self.label.setFont(QFont('SansSerif', 11))
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.label)
        hbox1.addStretch(1)

        self.toggle_button = QPushButton('最前面', self)
        self.toggle_button.setFont(QFont('SansSerif', 11))
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self.toggle_always_on_top)
        hbox1.addWidget(self.toggle_button)

        self.timer_combobox = QComboBox()
        self.timer_combobox.addItems(["0", "500", "1000"])
        self.timer_combobox.setFont(QFont('SansSerif', 11))
        self.timer_combobox.setCurrentIndex(1)
        self.timer_combobox.currentTextChanged.connect(self.update_timer)
        hbox1.addWidget(self.timer_combobox)

        self.timer_label = QLabel("ms")
        self.timer_label.setFont(QFont('SansSerif', 12))
        
        hbox1.addWidget(self.timer_label)
        layout.addLayout(hbox1)

        hbox = QHBoxLayout()
        self.qword = QLabel()
        self.qword.setFont(QFont('SansSerif', 14))
        hbox.addWidget(self.qword)
        hbox.addStretch(1)

        self.font_combobox = QComboBox()
        self.font_combobox.addItems(["10", "12", "14", "16"])
        self.font_combobox.setCurrentIndex(2)
        self.font_combobox.setFont(QFont('SansSerif', 14))
        self.font_combobox.currentTextChanged.connect(self.update_fontsize)
        hbox.addWidget(self.font_combobox)

        self.combobox = QComboBox()
        self.combobox.addItems(["10", "20", "30"])
        self.combobox.setFont(QFont('SansSerif', 14))
        self.combobox.currentTextChanged.connect(self.update_top)
        hbox.addWidget(self.combobox)

        layout.addLayout(hbox)

        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont('SansSerif', 14))
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)
        
        self.setLayout(layout)

        self.setWindowTitle("住所検索結果")
        self.setGeometry(1400, 100, 500, 200)
        self.setFixedSize(520,200)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(500)  # 500ミリ秒ごとにクリップボードをチェック

    def update_timer(self, value):
        if value == "0":
            self.timer.stop()
            self.qword.setText("- 停止中 -")
        else:
            self.timer.start(int(value))
            self.qword.setText("")

    def update_top(self):
        clipboard = pyperclip.paste()
        top = int(self.combobox.currentText())
        results = self.searcher.search(self.last_qword, self.threshold, top)
        self.update_results(results)
        self.update_qlabel(self.last_qword)

    def update_fontsize(self):
        size = int(self.font_combobox.currentText())
        self.list_widget.setFont(QFont('SansSerif', size))
        clipboard = pyperclip.paste()
        top = self.top
        results = self.searcher.search(self.last_qword, self.threshold, top)
        self.update_results(results)
        self.update_qlabel(self.last_qword)

    def update_qlabel(self, words):
        switch = words[-1]
        if (switch == "f" or switch == "r"):
            words = words[:-1] + " /" + switch
        self.qword.setText(words)

    def check_clipboard(self):
        clipboard = pyperclip.paste()
        if clipboard == "" or "\n" in clipboard:
            return
        if clipboard != self.last_clipboard:
            self.update_qlabel(clipboard)
            self.last_clipboard = clipboard
            top = int(self.combobox.currentText())
            results = self.searcher.search(clipboard, self.threshold, top)
            if results:
                self.last_qword = clipboard

            self.update_results(results)

    def update_results(self, results):
        self.list_widget.clear()
        for result, ratio in results:
            if (ratio == 0):
                self.list_widget.addItem(f"{result}")
            else:
                self.list_widget.addItem(f"{result}  ({ratio})")

    def update_threshold(self, value):
        self.threshold = value
        self.threshold_value_label.setText(str(value))

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        if self.always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.toggle_button.setText('最前面')
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.toggle_button.setText('最前面')

        self.show()  # ウィンドウを再表示して変更を適用


if __name__ == "__main__":
    csv_file = "/utf_ken_all.csv"  # CSVファイルのパスを指定
    dirname =  os.path.dirname(__file__)
    searcher = AddressSearcher(dirname + csv_file)
    
    app = QApplication(sys.argv)
    ex = AddressSearchApp(searcher)
    ex.show()
    sys.exit(app.exec_())