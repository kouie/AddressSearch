import csv
import re
import os
from fuzzywuzzy import fuzz
import pyperclip
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QListWidget, QLabel, QSlider, QHBoxLayout, QComboBox, QPushButton
from PyQt5.QtCore import QTimer, Qt, QSettings, QPoint, QSize
import sys
from PyQt5.QtGui import QFont



class AddressSearcher:
    def __init__(self, csv_file):
        self.addresses = self.load_addresses(csv_file)
        self.ignore_aza = True
        self.results_index = []
        self.filter = {'postal':0, 'kanji1':1, 'kanji2':1, 'kanji3':1}
        self.copy_filter = {'postal':0, 'kanji1':1, 'kanji2':1, 'kanji3':1}

    def load_addresses(self, csv_file):
        addresses = []
        address = {}
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
#            next(reader)  # ヘッダーをスキップ
            id=0
            for row in reader:
                kana_address = ''.join(row[3:6])
                kanji_address = ''.join(row[6:9])
                address = { 'id':id, 'postal':row[2], 'kana1':row[3], 'kana2':row[4], 'kana1':row[5],
                           'kanji1':row[6], 'kanji2':row[7], 'kanji3':row[8],
                           'kana':kana_address, 'kanji':kanji_address
                           }
                id += 1
                addresses.append(address)
        return addresses

    def search(self, query, threshold=70, top=20):
        switch = query[-1]
        self.results_index = []

        if (switch == "r"):
            query = query[:-1]
            results = []
            for each_address in self.addresses:
                kanji_address = each_address['kanji']                
                normalized_kanji = self.normalize(kanji_address)
                result = re.search(query, normalized_kanji)
                if result:
                    adr = self.generate_address(each_address['id'], self.filter, 1)
                    results.append((adr, 0))
                    self.results_index.append(each_address['id'])
        else:
            query = self.q_normalize(query)
            results = []
            queries = query.split(' ')
            for each_address in self.addresses:
                kanji_address = each_address['kanji']
                normalized_kanji = self.normalize(kanji_address)
                if all(w in normalized_kanji for w in queries):
                    adr = ' '.join([each_address[key] for key in each_address if self.filter.get(key) == 1])
                    results.append((adr, 0))
                    self.results_index.append(each_address['id'])

        return results[:top]

    def f_search(self, query, threshold=70):
        query = self.normalize(query)
        if (',' in query):
            fix, query = query.split(',')
        else:
            fix = ''

        results = []
        for postal_code, kana_address, kanji_address in self.addresses:

            if (fix != '' and fix not in kanji_address):
                continue
            if (len(query) > len(kanji_address)):
                continue

            normalized_kanji = self.normalize(kanji_address)
            kanji_ratio = fuzz.partial_ratio(query, normalized_kanji)

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
        if self.ignore_aza == True:
            text = text.replace('字','')
        text = re.sub(r'\d+', lambda m: str(int(m.group())), text)
        return text.lower()

    def generate_address(self, index, filter, delimiter):
        selected_address = [d for d in self.addresses if d['id'] == index][0]
        if delimiter == 1:
            adr = ' '.join([selected_address[key] for key in selected_address if filter.get(key) == 1])
        else:
            adr = ''.join([selected_address[key] for key in selected_address if filter.get(key) == 1])
            
        return adr

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

        hbox_lower1 = QHBoxLayout()

        self.display_label = QLabel("表示: ")
        self.display_label.setFont(QFont('SansSerif', 12))
        hbox_lower1.addWidget(self.display_label)

        self.toggle_pos_button = QPushButton('〒', self)
        self.toggle_prf_button = QPushButton('県', self)
        self.toggle_cty_button = QPushButton('市区', self)
        self.toggle_cnt_button = QPushButton('町', self)
        self.toggle_pos_button.setCheckable(True)
        self.toggle_pos_button.setChecked(False)
        self.toggle_prf_button.setCheckable(True)
        self.toggle_prf_button.setChecked(True)
        self.toggle_cty_button.setCheckable(True)
        self.toggle_cty_button.setChecked(True)
        self.toggle_cnt_button.setCheckable(True)
        self.toggle_cnt_button.setChecked(True)
        hbox_lower1.addWidget(self.toggle_pos_button)
        hbox_lower1.addWidget(self.toggle_prf_button)
        hbox_lower1.addWidget(self.toggle_cty_button)
        hbox_lower1.addWidget(self.toggle_cnt_button)
        self.toggle_pos_button.clicked.connect(self.update_filter)
        self.toggle_prf_button.clicked.connect(self.update_filter)
        self.toggle_cty_button.clicked.connect(self.update_filter)
        self.toggle_cnt_button.clicked.connect(self.update_filter)


        hbox_lower1.addStretch(1)

        self.toggle_aza_button = QPushButton('「字」を無視', self)
        self.toggle_aza_button.adjustSize()
        self.toggle_aza_button.setFont(QFont('SansSerif', 11))
        self.toggle_aza_button.setCheckable(True)
        self.toggle_aza_button.setChecked(True)
        self.toggle_aza_button.clicked.connect(self.update_ignore_aza)
        hbox_lower1.addWidget(self.toggle_aza_button)
        layout.addLayout(hbox_lower1)

        self.setLayout(layout)

        hbox_lower2 = QHBoxLayout()
        self.copy_button = QPushButton('選択行をコピー', self)
        self.copy_button.setMinimumWidth(100)
        self.copy_button.setFont(QFont('SansSerif', 11))
        self.copy_button.clicked.connect(self.copy_address)
        hbox_lower2.addWidget(self.copy_button)

        self.copy_label = QLabel(" コピー対象:")
        self.copy_label.setFont(QFont('SansSerif', 9))
        hbox_lower2.addWidget(self.copy_label)

        font = QFont('SansSerif', 8)
        self.copy_pos_button = QPushButton('〒', self)
        self.copy_prf_button = QPushButton('県', self)
        self.copy_cty_button = QPushButton('市区', self)
        self.copy_cnt_button = QPushButton('町', self)
        self.copy_spc_button = QPushButton('スペースつき', self)
        self.copy_pos_button.setCheckable(True)
        self.copy_pos_button.setChecked(False)
        self.copy_pos_button.setMaximumWidth(40)
        self.copy_prf_button.setCheckable(True)
        self.copy_prf_button.setChecked(True)
        self.copy_prf_button.setMaximumWidth(40)
        self.copy_cty_button.setCheckable(True)
        self.copy_cty_button.setChecked(True)
        self.copy_cty_button.setMaximumWidth(40)
        self.copy_cnt_button.setCheckable(True)
        self.copy_cnt_button.setChecked(True)
        self.copy_cnt_button.setMaximumWidth(40)
        self.copy_spc_button.setCheckable(True)
        self.copy_spc_button.setChecked(True)
        self.copy_pos_button.setFont(font)
        self.copy_prf_button.setFont(font)
        self.copy_cty_button.setFont(font)
        self.copy_cnt_button.setFont(font)

        hbox_lower2.addWidget(self.copy_pos_button)
        hbox_lower2.addWidget(self.copy_prf_button)
        hbox_lower2.addWidget(self.copy_cty_button)
        hbox_lower2.addWidget(self.copy_cnt_button)
        hbox_lower2.addWidget(self.copy_spc_button)

        self.copy_cnt_button.adjustSize()

        hbox_lower2.addStretch(1)
        layout.addLayout(hbox_lower2)

        self.setLayout(layout)


        self.setWindowTitle("住所検索")
#        self.setGeometry(1400, 100, 500, 200)
#        self.setFixedSize(520,300)

        self.settings = QSettings('address_search.ini', QSettings.IniFormat)
        self.resize(self.settings.value("size", QSize(520, 300)))
        self.move(self.settings.value("pos", QPoint(50, 50)))
        self.load_settings()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_clipboard)
        self.timer.start(500)  # 500ミリ秒ごとにクリップボードをチェック

    def load_settings(self):
        # ウィンドウ位置とサイズを復元
        self.resize(self.settings.value("size", self.size()))
        self.move(self.settings.value("pos", self.pos()))

    def closeEvent(self, event):
        # ウィンドウ位置とサイズを保存
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        super().closeEvent(event)

    def update_timer(self, value):
        if value == "0":
            self.timer.stop()
            self.qword.setText("- 停止中 -")
        else:
            self.timer.start(int(value))
            self.qword.setText("")

    def update_top(self):
        top = int(self.combobox.currentText())
        self.top = top
        self.update_results_display()
        self.update_qlabel(self.last_qword)

    def update_fontsize(self):
        size = int(self.font_combobox.currentText())
        self.list_widget.setFont(QFont('SansSerif', size))
        self.update_results_display()
        self.update_qlabel(self.last_qword)

    def update_qlabel(self, words):
        switch = words[-1]
        if switch == "r":
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

    def get_filter(self):
        filter = {}
        filter['postal'] = self.toggle_pos_button.isChecked()
        filter['kanji1'] = self.toggle_prf_button.isChecked()
        filter['kanji2'] = self.toggle_cty_button.isChecked()
        filter['kanji3'] = self.toggle_cnt_button.isChecked()

        return filter

    def update_results_display(self):
        self.list_widget.clear()
        filter = self.get_filter()
        counter = 0
        for index in self.searcher.results_index:
            each_address = self.searcher.generate_address(index, filter, 1)
            self.list_widget.addItem(f"{each_address}")
            counter += 1
            if counter > self.top:
                return

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

    def update_ignore_aza(self):
        self.searcher.ignore_aza = self.toggle_aza_button.isChecked()
        word = pyperclip.paste()

        top = self.top
        results = self.searcher.search(word, self.threshold, top)
        self.update_results(results)
        self.update_qlabel(word)

    def update_filter(self):
        filter = self.get_filter()
        self.searcher.filter = filter

        word = pyperclip.paste()

        self.update_results_display()
        self.update_qlabel(word)

    def copy_address(self):
        filter = {}
        filter['postal'] = self.copy_pos_button.isChecked()
        filter['kanji1'] = self.copy_prf_button.isChecked()
        filter['kanji2'] = self.copy_cty_button.isChecked()
        filter['kanji3'] = self.copy_cnt_button.isChecked()

        delimiter = self.copy_spc_button.isChecked()

        current_index = self.list_widget.currentRow()
        if current_index != -1:
            list_index = self.searcher.results_index[current_index]
            current = self.searcher.generate_address(list_index, filter, delimiter)

            self.last_clipboard = current
            pyperclip.copy(current)
            print(current)


if __name__ == "__main__":
    csv_file = "/utf_ken_all.csv"  # CSVファイルのパスを指定
    dirname =  os.path.dirname(__file__)
    searcher = AddressSearcher(dirname + csv_file)
    
    app = QApplication(sys.argv)
    ex = AddressSearchApp(searcher)
    ex.show()
    sys.exit(app.exec_())