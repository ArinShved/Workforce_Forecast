from pickle import TRUE
import sys
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QTabWidget, QVBoxLayout, QLabel,
    QWidget, QPushButton, QTextEdit, QSplitter, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout
)
from PySide6.QtGui import QAction,  QFont
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import psycopg2
import pandas as pd
from io import StringIO
import contextlib
import numpy as np
import configparser

    

from analyse_graduation import EducationFlowAnalyser
from analyse_profession import ProfessionAnalyser
from graf_graduation import plot_deficit_by_field, plot_forecast_graduates_graf, plot_full_admission_analysis,  plot_admission_chart, plot_graduation_chart
from graf_market import plot_market_chart, get_average_salary, plot_salary_chart
from prognose import ScenarioAnalyser


class MyMainWindow(QMainWindow):
    

    def __init__(self):
        """
        Инициализирует главное окно, подключается к БД и создаёт вкладки.
        """

        super().__init__()
        self.setWindowTitle("ИТР: Анализ и прогнозирование")
        self.resize(1200, 800)  # Ширина 1200, высота 800
        self.setMinimumSize(1100, 600) # Минимальный размер окна

        # Подключение к PostgreSQL
        config = configparser.ConfigParser()
        config.read('data.ini')
       
        self.conn = psycopg2.connect(
            host=config['Database']['host'],
            database=config['Database']['dbname'],
            user=config['Database']['user'],
            password=config['Database']['password'],
            port=config['Database'].getint('port')
        )
        
        # Меню приложения
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&Файл")
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        
        # Вкладки
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        
        # Вкладка 1
        tab1 = QWidget()
        tabs.addTab(tab1, "Приём / Выпуск")
        self.setup_admission_tab(tab1)
        
        # Вкладка 2
        tab2 = QWidget()
        tabs.addTab(tab2, "Дефицит кадров")
        self.setup_deficit_tab(tab2)

        # Вкладка 3
        tab3 = QWidget()
        tabs.addTab(tab3, "Рынок по должностям")
        self.setup_market_tab(tab3)

        # Вкладка 4
        tab4 = QWidget()
        tabs.addTab(tab4, "Сценарный прогноз")
        self.setup_forecast_tab(tab4)

        
        
    def on_tab_changed(self, index):
        """Очищает вывод при смене вкладки"""
        self.clear_output()
    
      # Добавляем заголовок для активной вкладки
        if index == 0:
          self.print_to_output("Вкладка: Приём / Выпуск")
        else:
          self.print_to_output("Вкладка: Дефицит кадров")

   #Настройка 1 вкладки
    def setup_admission_tab(self, widget):
        layout = QVBoxLayout(widget)
        
        btn_frame = QWidget()
        btn_layout = QVBoxLayout(btn_frame)

        # Кнопка для обновления графика
        refresh_btn = QPushButton("Обновить график")
        refresh_btn.clicked.connect(self.update_admission_graph)
        btn_layout.addWidget(refresh_btn)

        # Кнопка "Подробнее"
        detail_btn = QPushButton("Подробнее...")
        detail_btn.clicked.connect(self.show_analysis_graduat)
        btn_layout.addWidget(detail_btn)

        layout.addWidget(btn_frame)
        
        # Область для графика
        self.figure1 = Figure(figsize=(10, 14))
        self.canvas1 = FigureCanvas(self.figure1)
        self.canvas1.setMinimumHeight(500)
        layout.addWidget(self.canvas1)
        
        # Окно вывода 
        self.output_text1 = QTextEdit()
        self.output_text1.setFont(QFont("Courier", 10))
        self.output_text1.setMinimumHeight(100)
        self.output_text1.setPlaceholderText("Статистика по приёму и выпуску...")
        layout.addWidget(self.output_text1)

        
        self.update_admission_graph()
    
    def update_admission_graph(self):
        """
        Обновляет графики приёма, выпуска и прогноза выпуска.
        """
        try:         
            analyser = EducationFlowAnalyser()
            analyser.connect()

            df = analyser.get_admission_data(top_n=5)
            output_text = analyser.admis_report(df, top_n=5)
            
            # Отображение статистики
            self.output_text1.clear()
            
            for line in output_text.split('\n'):
                if line.strip():
                    self.output_text1.append(line)

            # Построение графиков
            if df is not None and not df.empty:
               
                self.figure1.clear()

                ax1 = self.figure1.add_subplot(3, 1, 1)
                ax2 = self.figure1.add_subplot(3, 1, 2)
                ax3 = self.figure1.add_subplot(3, 1, 3)
                
                plot_admission_chart(ax1, df)
                plot_graduation_chart(ax2, df)

                plot_forecast_graduates_graf(ax3, analyser, start_year=2025, years_ahead=4)
                
                self.figure1.subplots_adjust(left=0.05, right=0.9, top=0.93, bottom=0.08, hspace=0.35)                
                
                self.canvas1.draw()

                analyser.disconnect()
                
        except Exception as e:
            print(f"Ошибка при загрузке графика: {e}")
    #2 Настройка 2 ыкладка
    def setup_deficit_tab(self, widget):
        layout = QVBoxLayout(widget)
        
        # Кнопка для обновления графика
        refresh_btn = QPushButton("Обновить график дефицита")
        refresh_btn.clicked.connect(self.update_deficit_graph)
        layout.addWidget(refresh_btn)

        #Knopka dlya analysa
        detail_deficit_btn = QPushButton("Подробный анализ дефицита профессий")
        detail_deficit_btn.clicked.connect(self.show_analysis_prof)
        layout.addWidget(detail_deficit_btn)
        
        # Место для графика
        self.figure2 = Figure(figsize=(10, 12))
        self.canvas2 = FigureCanvas(self.figure2)
        self.canvas2.setMinimumHeight(500)
        layout.addWidget(self.canvas2)
        
        # окно вывода для этой вкладки
        self.output_text2 = QTextEdit()
        self.output_text2.setFont(QFont("Courier", 10))
        self.output_text2.setMinimumHeight(150)
        self.output_text2.setPlaceholderText("Статистика по дефициту кадров...")
        layout.addWidget(self.output_text2)

        # Загружаем начальные данные
        self.update_deficit_graph()
    
    def update_deficit_graph(self):
        
        try:
            with contextlib.redirect_stdout(StringIO()) as fake_output:
                analyser = EducationFlowAnalyser()
                analyser.connect()  

                self.figure2.clear()
                ax = self.figure2.add_subplot(111)
        
                
                df = plot_deficit_by_field(analyser, ax=ax, show_plot=False, target_year=2025)
                output_text = fake_output.getvalue()

                
                analyser.disconnect()
            
            # Выводим захваченный текст
                self.output_text2.clear()
                if output_text:
                    for line in output_text.split('\n'):
                        if line.strip():
                           self.output_text2.append(line)
            
            self.canvas2.draw()
                            
        except Exception as e:
            print(f"Ошибка при загрузке графика дефицита: {e}")

    # 3 vkladka
    def setup_market_tab(self, widget):
     layout = QVBoxLayout(widget)

     btn_frame = QWidget()
     btn_layout = QHBoxLayout(btn_frame)
    
     # Кнопка для переключения на график должностей
     self.btn_market = QPushButton("Рынок по должностям")
     self.btn_market.clicked.connect(lambda: self.switch_market_chart('market'))
     btn_layout.addWidget(self.btn_market)
    
    # Кнопка для переключения на график зарплат
     self.btn_salary = QPushButton("Зарплаты по профессиям")
     self.btn_salary.clicked.connect(lambda: self.switch_market_chart('salary'))
     btn_layout.addWidget(self.btn_salary)
    
    # Кнопка обновления
     refresh_btn = QPushButton("Обновить")
     refresh_btn.clicked.connect(self.update_market_graph)
     btn_layout.addWidget(refresh_btn)

     layout.addWidget(btn_frame)
    
     # Место для графика
     self.figure3 = Figure(figsize=(12, 8))
     self.canvas3 = FigureCanvas(self.figure3)
     self.canvas3.setMinimumHeight(500)
     layout.addWidget(self.canvas3)
    
    # Окно вывода для этой вкладки
     self.output_text3 = QTextEdit()
     self.output_text3.setFont(QFont("Courier", 10))
     self.output_text3.setMinimumHeight(150)
     self.output_text3.setPlaceholderText("Статистика по должностям...")
     self.current_market_mode = 'market'
     layout.addWidget(self.output_text3)
    
     self.update_market_graph()

    def update_market_graph(self):
     try:
        if self.current_market_mode == 'market':
            with contextlib.redirect_stdout(StringIO()) as fake_output:
                self.figure3.clear()
                ax = self.figure3.add_subplot(111)

                df = plot_market_chart(self.conn,ax=ax, show_plot=False)
                output_text = fake_output.getvalue()
        
            self.output_text3.clear()
            if output_text:
                for line in output_text.split('\n'):
                    if line.strip():
                        self.output_text3.append(line)
        
            self.figure3.subplots_adjust(bottom=0.40)
            self.canvas3.draw()
        else:
            with contextlib.redirect_stdout(StringIO()) as fake_output:
                df = get_average_salary(self.conn, top_n=20)
                output_text = fake_output.getvalue()
            
            self.output_text3.clear()
            if output_text:
                for line in output_text.split('\n'):
                    if line.strip():
                        self.output_text3.append(line)
            
            self.figure3.clear()
            ax = self.figure3.add_subplot(111)
            plot_salary_chart(df, ax=ax)
            self.figure3.subplots_adjust(left=0.25, right=0.95, top=0.95, bottom=0.05)

            self.canvas3.draw()
        
     except Exception as e:
        self.output_text3.append(f"Ошибка: {e}")
    
   
    def setup_forecast_tab(self, widget):
        layout = QVBoxLayout(widget)
    
        type_frame = QWidget()
        type_layout = QHBoxLayout(type_frame)
    
        type_layout.addWidget(QLabel("Тип анализа:"))
        self.analysis_type_combo = QComboBox()
        self.analysis_type_combo.addItem("По направлениям подготовки (специальностям)")
        self.analysis_type_combo.addItem("По профессиям")
        self.analysis_type_combo.currentIndexChanged.connect(self.on_analysis_type_changed)
        type_layout.addWidget(self.analysis_type_combo)
    
        layout.addWidget(type_frame)

        selection_frame = QWidget()
        selection_layout = QHBoxLayout(selection_frame)
    
        # Выпадающий список для выбора специальности
        selection_layout.addWidget(QLabel("Выберите специальность/профессию:"))
        self.forecast_code_combo = QComboBox()
        self.forecast_code_combo.addItem("Все (стандартный режим)")
        selection_layout.addWidget(self.forecast_code_combo)

            
        layout.addWidget(selection_frame)

        # Кнопка для запуска анализа
        refresh_btn = QPushButton("Запустить сценарный анализ")
        refresh_btn.clicked.connect(self.update_forecast_graph)
        layout.addWidget(refresh_btn)
    
        # Место для графика 
        self.figure4 = Figure(figsize=(14, 10))
        self.canvas4 = FigureCanvas(self.figure4)
        self.canvas4.setMinimumHeight(500)
        layout.addWidget(self.canvas4)
    
        # Окно вывода
        self.output_text4 = QTextEdit()
        self.output_text4.setFont(QFont("Courier", 10))
        self.output_text4.setMinimumHeight(150)
        layout.addWidget(self.output_text4)

        self.current_analysis_type = 'study_field'
    
        # Загружаем начальные данные
        self.update_forecast_specialties()
        #self.update_forecast_graph()

    def update_forecast_graph(self):
        """Запускает сценарный анализ и отображает результаты"""
        try:
            
            analyser = ScenarioAnalyser(self.conn)
        
            # Запускаем анализ
            if self.current_analysis_type == 'study_field':
                results = analyser.run_scenario_analysis(years_ahead=5, use_weighted=True, min_relevance=85)
                title_prefix = "направлений подготовки"
                report_type = 'study_field'
            else:
                results = analyser.run_scenario_analysis_by_profession(years_ahead=5, min_relevance=85)
                title_prefix = "профессий"
                report_type = 'profession'
        
        

            if results:
                # Сохраняем результаты для возможного использования
                self.forecast_results = results

                with contextlib.redirect_stdout(StringIO()) as fake_output:
                    analyser.generate_scenario_report(results, report_type)
                    output_text = fake_output.getvalue()
            
                self.output_text4.clear()
                self.output_text4.append(output_text)
            
                # Получаем выбранную специальность
                selected_index = self.forecast_code_combo.currentIndex()
                selected_code = self.forecast_code_combo.currentData() if selected_index > 0 else None
            
                # Очищаем фигуру
                self.figure4.clear()

                original_show = plt.show
                plt.show = lambda: None
            
            # Вызываем метод с передачей параметров
                analyser.plot_scenario_comparison(results, self.figure4, top_n=6, selected_code=selected_code)
                
                self.canvas4.draw()
          
                self.canvas4.draw()

            
        except Exception as e:
            self.output_text4.append(f"Ошибка: {e}")

    def update_forecast_specialties(self):
         """Обновляет список для выбора"""
         try:
            analyser = ScenarioAnalyser(self.conn)
        
            if self.current_analysis_type == 'study_field':
                results = analyser.run_scenario_analysis(years_ahead=5, use_weighted=True, min_relevance=85)
                type_name = "специальности"
                do_code = True
            else:
                results = analyser.run_scenario_analysis_by_profession(years_ahead=5, min_relevance=80)
                type_name = "профессии"
                do_code = False
        
            if results:
                self.forecast_results = results
                current_text = self.forecast_code_combo.currentText()
                current_data = self.forecast_code_combo.currentData()
            
                self.forecast_code_combo.clear()
                self.forecast_code_combo.addItem(f"Все {type_name} (стандартный режим)")
            
                # Сортируем по вакансиям
                sorted_fields = sorted(results.items(), 
                                       key=lambda x: x[1]['current_vacancies'], 
                                       reverse=True)
            
                for code, data in sorted_fields:
                    if(do_code):
                        display_text = f"{code} - {data['name'][:90]}"
                    else:
                        display_text = f"{data['name'][:90]}"
                    self.forecast_code_combo.addItem(display_text, code)
            
                # Восстанавливаем выбор
                index = self.forecast_code_combo.findData(current_data)
                if index >= 0:
                    self.forecast_code_combo.setCurrentIndex(index)
                else:
                    for i in range(self.forecast_code_combo.count()):
                        if self.forecast_code_combo.itemText(i) == current_text:
                            self.forecast_code_combo.setCurrentIndex(i)
                            break
    
         except Exception as e:
            self.output_text4.append(f"Ошибка при загрузке списка: {e}")

    def plot_existing_comparison(self, results):
      
            
        analyzer = ScenarioAnalyser(self.conn)
    
        # Берём топ-6 направлений
        sorted_fields = sorted(results.items(), 
                               key=lambda x: x[1]['current_vacancies'], 
                               reverse=True)[:6]
    
        scenarios = list(analyzer.scenarios.keys())
    
        # 1. Сводная таблица дефицита по сценариям
        ax1 = self.figure4.add_subplot(2, 3, 1)
        x = np.arange(len(scenarios))
        width = 0.25
    
        for i, (code, data) in enumerate(sorted_fields[:4]):
            balances = []
            for s in scenarios:
                forecast = data['forecasts'][s]
                balances.append(forecast[-1]['balance'] if forecast else 0)
            offset = (i - 2) * width
            ax1.bar(x + offset, balances, width, label=code, alpha=0.8)
    
        ax1.axhline(y=0, color='black', linewidth=2)
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenarios)
        ax1.set_ylabel('Баланс (чел.)')
        ax1.set_title('Прогноз баланса через 5 лет')
        ax1.legend(loc='best', fontsize=8)
        ax1.grid(True, alpha=0.3)
    
        # 2. Динамика по базовому сценарию (топ-1)
        ax2 = self.figure4.add_subplot(2, 3, 2)
        code, data = sorted_fields[0]
        base_forecast = data['forecasts']['Базовый']
        if base_forecast:
            years = [f['year'] for f in base_forecast]
            supply = [f['supply'] for f in base_forecast]
            demand = [f['demand'] for f in base_forecast]
        
            ax2.plot(years, supply, 'o-', label='Предложение', color='green', linewidth=2)
            ax2.plot(years, demand, 's-', label='Спрос', color='red', linewidth=2)
            ax2.fill_between(years, supply, demand, 
                             where=(np.array(supply) < np.array(demand)),
                             color='red', alpha=0.3, label='Дефицит')
            ax2.set_xlabel('Год')
            ax2.set_ylabel('Количество')
            ax2.set_title(f'Базовый сценарий: {code}')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
    
        # 3. Сравнение сценариев
        ax3 = self.figure4.add_subplot(2, 3, 3)
        colors = [analyzer.scenarios[s]['color'] for s in scenarios]
        for s, color in zip(scenarios, colors):
            forecast = data['forecasts'][s]
            if forecast:
                years = [f['year'] for f in forecast]
                balances = [f['balance'] for f in forecast]
                ax3.plot(years, balances, 'o-', color=color, label=s, linewidth=2)
    
        ax3.axhline(y=0, color='black', linestyle='--')
        ax3.set_xlabel('Год')
        ax3.set_ylabel('Баланс (чел.)')
        ax3.set_title(f'Сравнение сценариев: {code}')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
        # 4. Тепловая карта
        ax4 = self.figure4.add_subplot(2, 3, 4)
        deficit_matrix = []
        labels = []
        for code, data in sorted_fields[:6]:
            row = [data['forecasts'][s][-1]['balance'] if data['forecasts'][s] else 0 for s in scenarios]
            deficit_matrix.append(row)
            labels.append(code)
    
        im = ax4.imshow(deficit_matrix, cmap='RdYlGn_r', aspect='auto')
        ax4.set_xticks(range(len(scenarios)))
        ax4.set_xticklabels(scenarios, rotation=45, ha='right')
        ax4.set_yticks(range(len(labels)))
        ax4.set_yticklabels(labels)
        ax4.set_title('Тепловая карта дефицита')
        plt.colorbar(im, ax=ax4)
    
        # 5. Текущее состояние
        ax5 = self.figure4.add_subplot(2, 3, 5)
        codes = [code for code, _ in sorted_fields[:8]]
        vacancies = [data['current_vacancies'] for _, data in sorted_fields[:8]]
        graduates = [data['current_graduates'] for _, data in sorted_fields[:8]]
    
        x = np.arange(len(codes))
        width = 0.35
        ax5.bar(x - width/2, vacancies, width, label='Вакансии', color='#FF6B6B')
        ax5.bar(x + width/2, graduates, width, label='Выпускники', color='#45B7D1')
        ax5.set_xticks(x)
        ax5.set_xticklabels(codes, rotation=45, ha='right', fontsize=8)
        ax5.set_ylabel('Количество')
        ax5.set_title('Текущее состояние')
        ax5.legend()
    
        # 6. Риски и возможности (текст)
        ax6 = self.figure4.add_subplot(2, 3, 6)
        ax6.axis('off')
        risk_text = self.output_text4.toPlainText()[:500] + "..."
        ax6.text(0.05, 0.95, risk_text, transform=ax6.transAxes, fontsize=8,
                verticalalignment='top', fontfamily='monospace')
    
        self.figure4.tight_layout()
        self.canvas4.draw()
   
    def show_analysis_graduat(self):
        """Открывает новое окно с детальным анализом"""
        try:
           analyser = EducationFlowAnalyser()
           analyser.connect()
        
           with contextlib.redirect_stdout(StringIO()) as fake_output:
              report = analyser.generate_report([2023, 2024, 2025])
              
              
              analyser.print_detailed_by_year(2025, top_n =20, only_itr = True)
              output_text_2 = analyser.get_retention_summary(start_year= 2020, end_year=2021)
              print('\n')
              print(output_text_2)
              output_text = fake_output.getvalue()

           analyser.disconnect()
        
          # Новое окно
           detail_window = QMainWindow(self)
           detail_window.setWindowTitle("Детальный анализ приёма и выпуска")
           detail_window.resize(800, 600)
        
           text_edit = QTextEdit()
           text_edit.setFont(QFont("Courier", 10))
           text_edit.setPlainText(output_text)
        
           detail_window.setCentralWidget(text_edit)
           detail_window.show()
        
        except Exception as e:
          print(f"Ошибка: {e}")

    def show_analysis_prof(self):
        '''
        '''
        try:
            config = configparser.ConfigParser()
            config.read('data.ini')
       
        
            host=str(config['Database']['host'])
            database=str(config['Database']['dbname'])
            user=str(config['Database']['user'])
            password=str(config['Database']['password'])
            port=str(config['Database']['port'])
        
            conn_str = 'postgresql://' + user +':'+ password +'@' + host +':' + port +'/'+database
            analyser = ProfessionAnalyser(conn_str)



            #data = analyser.generate_report(only_itr=True)
            deficit_df = analyser.get_top_deficit_professions(limit=20)
            surplus_df = analyser.get_top_surplus_professions(limit=20)
        
            print(f"Дефицитных профессий: {len(deficit_df)}")
            print(f"Профицитных профессий: {len(surplus_df)}")

            # Создаем окно с вкладками
            detail_window = QMainWindow(self)
            detail_window.setWindowTitle("Анализ рынка ИТР-профессий")
            detail_window.resize(1200, 700)
        
            tabs = QTabWidget()
            detail_window.setCentralWidget(tabs)
        
            # Вкладка с дефицитными профессиями
            
            deficit_tab = QWidget()
            deficit_layout = QVBoxLayout(deficit_tab)
        
            if not deficit_df.empty:
                deficit_table = QTableWidget()
                deficit_table.setRowCount(len(deficit_df))
                deficit_table.setColumnCount(5)
                deficit_table.setHorizontalHeaderLabels(['Профессия', 'Вакансий', 'Безработных', 'Кандидатов на место', 'Зарплата'])
            
                for i, (_, row) in enumerate(deficit_df.iterrows()):
                    deficit_table.setItem(i, 0, QTableWidgetItem(row['profession']))
                    deficit_table.setItem(i, 1, QTableWidgetItem(str(int(row['open_vacancies']))))
                    deficit_table.setItem(i, 2, QTableWidgetItem(str(int(row['unemployed']))))
                
                    candidates = row['candidates_per_vacancy']
                    candidates_str = f"{candidates:.2f}" if candidates != float('inf') else "нет данных"
                    deficit_table.setItem(i, 3, QTableWidgetItem(candidates_str))
                    deficit_table.setItem(i, 4, QTableWidgetItem(f"{int(row['salary_avg']):,}"))
            
                deficit_table.setAlternatingRowColors(True)
                deficit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
                deficit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
                deficit_layout.addWidget(deficit_table)
            else:
                deficit_layout.addWidget(QLabel("Дефицитных ИТР-профессий не обнаружено"))
        
            tabs.addTab(deficit_tab, "Дефицитные профессии")
        
           
            surplus_tab = QWidget()
            surplus_layout = QVBoxLayout(surplus_tab)
        
            if not surplus_df.empty:
                surplus_table = QTableWidget()
                surplus_table.setRowCount(len(surplus_df))
                surplus_table.setColumnCount(5)
                surplus_table.setHorizontalHeaderLabels(['Профессия', 'Вакансий', 'Безработных', 'Кандидатов на место', 'Зарплата'])
            
                for i, (_, row) in enumerate(surplus_df.iterrows()):
                    surplus_table.setItem(i, 0, QTableWidgetItem(row['profession']))
                    surplus_table.setItem(i, 1, QTableWidgetItem(str(int(row['open_vacancies']))))
                    surplus_table.setItem(i, 2, QTableWidgetItem(str(int(row['unemployed']))))
                
                    candidates = row['candidates_per_vacancy']
                    candidates_str = f"{candidates:.0f}" if candidates != float('inf') else "нет данных"
                    surplus_table.setItem(i, 3, QTableWidgetItem(candidates_str))
                    surplus_table.setItem(i, 4, QTableWidgetItem(f"{int(row['salary_avg']):,}"))
            
                surplus_table.setAlternatingRowColors(True)
                surplus_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
                surplus_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
                surplus_layout.addWidget(surplus_table)
            else:
                surplus_layout.addWidget(QLabel("Профицитных ИТР-профессий не обнаружено"))
        
            tabs.addTab(surplus_tab, "Профицитные профессии")
        
            detail_window.show()
        
        except Exception as e:
            self.output_text2.append(f"Ошибка: {e}")
            print(f"Ошибка: {e}")

    def on_analysis_type_changed(self, index):
        """Обработчик изменения типа анализа"""
        if index == 0:
            self.current_analysis_type = 'study_field'
        else:
            self.current_analysis_type = 'profession'
        self.update_forecast_specialties()
        self.update_forecast_graph()

    def switch_market_chart(self, mode):
        """Переключает между графиками рынка и зарплат"""
        self.current_market_mode = mode
    
       
        if mode == 'market':
            self.btn_market.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            self.btn_salary.setStyleSheet("")
        else:
            self.btn_market.setStyleSheet("")
            self.btn_salary.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
    
        self.update_market_graph()

    def closeEvent(self, event):
        """Закрываем соединение с БД при выходе"""
        self.conn.close()
        event.accept()



# 2. Основная часть программы
if __name__ == "__main__":
   
    #  объект приложения
    app = QApplication(sys.argv)
    
    # экземпляр окна
    window = MyMainWindow()
   
    window.show()
    
    # Запуск главного цикла событий Qt 
    app.exec()