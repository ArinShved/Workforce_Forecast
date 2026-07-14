import pandas as pd
import psycopg2
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import mplcursors

class ScenarioAnalyser:
    """
    Сценарный анализ прогнозирования потребности в ИТР-кадрах
    """
    
    def __init__(self, conn):
        self.conn = conn
        
        # Параметры сценариев Курская область
        self.scenarios = {
            'Пессимистичный': {
                'economy_growth': -0.02,
                'attrition_rate': 0.10,
                'investment_scale': 0.7,
                'migration_balance': -0.05,
                'budget_change': -0.10,
                'student_outflow_rate': 0.22,
                'color': '#FF4444',
                'description': 'Экономический спад, сокращение инвестиций, отток кадров'
            },
            'Базовый': {
                'economy_growth': 0.028,
                'attrition_rate': 0.07,
                'investment_scale': 0.93,
                'migration_balance': 0.0,
                'budget_change': 0.0,
                'student_outflow_rate': 0.18,
                'color': '#FFD700',
                'description': 'Умеренный рост экономики, стабильная ситуация'
            },
            'Оптимистичный': {
                'economy_growth': 0.04,
                'attrition_rate': 0.05,
                'investment_scale': 1.2,
                'migration_balance': 0.02,
                'budget_change': 0.05,
                'student_outflow_rate': 0.14,
                'color': '#44FF44',
                'description': 'Быстрый экономический рост, новые инвестиции, приток кадров'
            }
        }
    

     
    def get_current_data(self, quiet=True):
     """
    Получение текущих данных для прогноза с распределением по весам
      """
     query = """
        WITH high_relevance_links AS (
    SELECT 
        position_id,
        study_field_id,
        relevance_score
    FROM position_study_field
    WHERE relevance_score > 50
),
-- Считаем общий вес для каждой профессии
position_weights AS (
    SELECT 
        position_id,
        SUM(relevance_score) as total_weight
    FROM high_relevance_links
    GROUP BY position_id
),
-- Распределяем вакансии по направлениям пропорционально весу
weighted_vacancies AS (
    SELECT 
        hrl.study_field_id,
        SUM(lb.active_vacancies * (hrl.relevance_score * 1.0 / NULLIF(pw.total_weight, 0))) as current_vacancies
    FROM labor_market_balance lb
    JOIN high_relevance_links hrl ON lb.position_id = hrl.position_id
    JOIN position_weights pw ON hrl.position_id = pw.position_id
    WHERE pw.total_weight > 0
    GROUP BY hrl.study_field_id
),
-- Распределяем безработных
weighted_unemployed AS (
    SELECT 
        hrl.study_field_id,
        SUM(lb.unemployed_count * (hrl.relevance_score * 1.0 / NULLIF(pw.total_weight, 0))) as current_unemployed
    FROM labor_market_balance lb
    JOIN high_relevance_links hrl ON lb.position_id = hrl.position_id
    JOIN position_weights pw ON hrl.position_id = pw.position_id
    WHERE pw.total_weight > 0
    GROUP BY hrl.study_field_id
),
-- Распределяем штат
weighted_staff AS (
    SELECT 
        hrl.study_field_id,
        SUM(sf.staff_count * (hrl.relevance_score * 1.0 / NULLIF(pw.total_weight, 0))) as current_staff
    FROM staff_fact sf
    JOIN high_relevance_links hrl ON sf.position_id = hrl.position_id
    JOIN position_weights pw ON hrl.position_id = pw.position_id
    WHERE pw.total_weight > 0
    GROUP BY hrl.study_field_id
),
current_graduates AS (
    SELECT 
        g.study_field_id,
        SUM(g.graduates_total) as current_graduates
    FROM graduations g
    WHERE g.year = (SELECT MAX(year) FROM graduations)
    GROUP BY g.study_field_id
)
SELECT 
    sf.id as field_id,
    sf.code,
    sf.name,
    sf.broad_group,
    ROUND(COALESCE(cg.current_graduates, 0)) as current_graduates,
    ROUND(COALESCE(wv.current_vacancies, 0)) as current_vacancies,
    ROUND(COALESCE(wu.current_unemployed, 0)) as current_unemployed,
    ROUND(COALESCE(ws.current_staff, 0)) as current_staff
FROM study_fields sf
LEFT JOIN current_graduates cg ON sf.id = cg.study_field_id
LEFT JOIN weighted_vacancies wv ON sf.id = wv.study_field_id
LEFT JOIN weighted_unemployed wu ON sf.id = wu.study_field_id
LEFT JOIN weighted_staff ws ON sf.id = ws.study_field_id
WHERE sf.is_itr = TRUE
  AND (cg.current_graduates > 0 OR COALESCE(wv.current_vacancies, 0) > 0)
ORDER BY current_vacancies desc
    """
    
     df = pd.read_sql(query, self.conn)
    
     if not quiet:
        print("\n Текушие данные:")
        for _, row in df.head(15).iterrows():
            print(f"{row['code']}: вакансий={row['current_vacancies']:.0f}, "
                  f"выпуск={row['current_graduates']}, "
                  f"безработных={row['current_unemployed']:.0f}, "
                  f"штат={row['current_staff']:.0f}")
    
    
     return df

    
    def get_current_data_weighted(self, min_relevance=50, quiet=True):
     """
    Получение данных с весами (только для профессий с реальными вакансиями)
    """
     query = f"""
WITH vacancies_with_data AS (
    SELECT DISTINCT
        lb.position_id,
        lb.active_vacancies,
        lb.unemployed_count
    FROM labor_market_balance lb
    WHERE lb.active_vacancies > 0
),
high_relevance_links AS (
    SELECT 
        psf.position_id,
        psf.study_field_id,
        psf.relevance_score
    FROM position_study_field psf
    JOIN vacancies_with_data vwd ON psf.position_id = vwd.position_id
    WHERE psf.relevance_score >= {min_relevance}
),
position_weights AS (
    SELECT 
        position_id,
        SUM(relevance_score) as total_weight
    FROM high_relevance_links
    GROUP BY position_id
),
weighted_vacancies AS (
    SELECT 
           
            hrl.study_field_id,
            SUM(vwd.active_vacancies) as current_vacancies
        FROM high_relevance_links hrl
        JOIN vacancies_with_data vwd ON hrl.position_id = vwd.position_id
        GROUP BY hrl.study_field_id
),
current_graduates AS (
    SELECT 
        g.study_field_id,
        SUM(g.graduates_total) as total_graduates
    FROM graduations g
    WHERE g.year = (SELECT MAX(year) FROM graduations)
    GROUP BY g.study_field_id
)
SELECT 
    sf.id as field_id,
    sf.code,
    sf.name,
    sf.broad_group,
    COALESCE(cg.total_graduates, 0) as current_graduates,
    ROUND(COALESCE(wv.current_vacancies, 0)) as current_vacancies,
    0 as current_unemployed,
    0 as current_staff
FROM study_fields sf
LEFT JOIN current_graduates cg ON sf.id = cg.study_field_id
LEFT JOIN weighted_vacancies wv ON sf.id = wv.study_field_id
WHERE sf.is_itr = TRUE
  AND (cg.total_graduates > 0 OR COALESCE(wv.current_vacancies, 0) > 0)
ORDER BY current_vacancies DESC
"""
    
     df = pd.read_sql(query, self.conn)
    
     if not quiet:
        print(f"\nТекущие данныЕ (только профессии с вакансиями, min_relevance={min_relevance}):")
        for _, row in df.head(15).iterrows():
            print(f"{row['code']}: вакансий={row['current_vacancies']:.0f}, выпуск={row['current_graduates']}")
     return df

    def get_current_data_by_profession(self, min_relevance=85, quiet=True):
        """
        Получение текущих данных для прогноза по профессиям
        """
        query = f"""
         WITH vacancies_with_data AS (
        SELECT 
            p.id as position_id,
            p.name as position_name,
            p.category,
            p.is_itr,
            SUM(lb.active_vacancies) as total_vacancies,
            SUM(lb.unemployed_count) as total_unemployed,
            AVG((lb.salary_min + lb.salary_max)/2) as avg_salary,
            COALESCE((
                SELECT SUM(sf.staff_count)
                FROM staff_fact sf
                WHERE sf.position_id = p.id
            ), 0) as total_staff  
        FROM labor_market_balance lb
        JOIN positions p ON lb.position_id = p.id
        WHERE lb.active_vacancies > 0
        GROUP BY p.id, p.name, p.category, p.is_itr
    )
    SELECT 
        vwd.position_id as field_id,
        vwd.position_name as code,
        vwd.position_name as name,
        vwd.category as broad_group,
        ROUND(COALESCE((
            SELECT SUM(g.graduates_total) 
            FROM position_study_field psf
            JOIN graduations g ON psf.study_field_id = g.study_field_id
            WHERE psf.position_id = vwd.position_id
            AND g.year >= EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 1
        ), 0)) as current_graduates,
        vwd.total_vacancies as current_vacancies,
        vwd.total_unemployed as current_unemployed,
        vwd.total_staff as current_staff  -- ДОБАВЛЯЕМ ШТАТ
    FROM vacancies_with_data vwd
    WHERE vwd.total_vacancies > 0
    ORDER BY current_vacancies DESC
        """
    
        df = pd.read_sql(query, self.conn)
    
        if not quiet:
            print(f"\nТекущие данные по профессиям (min_relevance={min_relevance}):")
            for _, row in df.head(15).iterrows():
                print(f"{row['code']}: вакансий={row['current_vacancies']:.0f}, "
                     # f"выпускников(связанных)={row['current_graduates']}, "
                      f"безработных={row['current_unemployed']:.0f}")
    
        return df

    def run_scenario_analysis_by_profession(self, years_ahead=5, min_relevance=90):
        """
        Запуск сценарного анализа по профессиям
        """
        current_data = self.get_current_data_by_profession(min_relevance)
    
        if current_data.empty:
            print("Нет данных для анализа по профессиям")
            return None
    
        results = {}
    
        for _, field in current_data.iterrows():
            field_results = {}
            for scenario in self.scenarios.keys():
                forecast = self.forecast_scenario(field, scenario, years_ahead)
                field_results[scenario] = forecast
            results[field['code']] = {
                'name': field['name'],
                'broad_group': field['broad_group'],
                'current_graduates': int(field['current_graduates']),
                'current_vacancies': int(field['current_vacancies']),
                'current_unemployed': int(field['current_unemployed']),
                'current_staff': int(field['current_staff']),
                'forecasts': field_results,
                'type': 'profession'
            }
    
        return results

    def forecast_scenario(self, field_data, scenario_name, years_ahead=5):
        params = self.scenarios[scenario_name]
    
        graduates = field_data['current_graduates']
        #print(graduates)
        
        vacancies = field_data['current_vacancies']
        unemployed = field_data['current_unemployed']
        staff = field_data['current_staff']
    
        graduate_trend = 0.07
        investments = {}
        field_code = field_data['code']
    
        forecast = []
        current_graduates = graduates
        current_vacancies = vacancies
        current_staff = staff
        remaining_unemployed = unemployed
    
        for year in range(1, years_ahead + 1):
            current_year = datetime.now().year + year
            #общее студентов
            budget_factor = 1 + params['budget_change']
            total_graduates = current_graduates * (1 + graduate_trend * year) * budget_factor
                    
        # ПРЕДЛОЖЕНИЕ (выпускники + безработные)
            
            employment_rate=0.33
            profile_match=0.55
            
            migration = 1 - params['student_outflow_rate']
            effective_graduate_rate = employment_rate * profile_match * migration

            supply_graduates = total_graduates * effective_graduate_rate
        
           
        # Безработные, готовые к трудоустройству 
            unemployed_relevance=0.7
            unemployed_ready = remaining_unemployed * unemployed_relevance * (1 + params['migration_balance'])
        
            total_supply = supply_graduates + unemployed_ready
        
        # СПРОС (вакансии + выбытие + новые места)
        # Если вакансий нет, спрос не растёт
            if current_vacancies > 0:
                demand_growth = current_vacancies * (1 + params['economy_growth']) 
            else:
            # Если вакансий нет, спрос формируется только за счёт выбытия и новых мест
                demand_growth = current_vacancies
        
            attrition = current_staff * params['attrition_rate']
             
                
        
            total_demand = demand_growth + attrition 

            # Сколько безработных найдут работу в этом году
            employed_from_unemployed = min(unemployed_ready, total_demand)
            remaining_unemployed = remaining_unemployed - employed_from_unemployed
            # Добавляем новых безработных из выпускников, которые не нашли работу
            unemployed_from_graduates = max(0, supply_graduates - (total_demand - employed_from_unemployed))
            remaining_unemployed += unemployed_from_graduates
        
        # Баланс (положительный = профицит, отрицательный = дефицит)
            balance = total_supply - total_demand

            if abs(balance) > total_demand * 0.5:
                balance = int(total_demand * 0.5) if balance > 0 else -int(total_demand * 0.5)
        
            forecast.append({
            'year': current_year,
            'supply': round(total_supply),
            'demand': round(total_demand),
            'attrition': round(attrition),
            'balance': round(balance),
            'status': 'Дефицит' if balance < 0 else 'Профицит'
            })
        
        # Обновляем для следующего года
            current_graduates = total_graduates
            #print(current_graduates)
            current_vacancies = demand_growth
            current_staff = current_staff  - attrition  + employed_from_unemployed + (supply_graduates * employment_rate)

                
        return forecast

    def run_scenario_analysis(self, years_ahead=5, use_weighted=False, min_relevance=80):
        """
        Запуск сценарного анализа для всех направлений
       
        """
             
                
        # Получаем текущие данные
        if use_weighted:
            current_data = self.get_current_data_weighted(min_relevance)
        else:
            current_data = self.get_current_data()
        
        if current_data.empty:
            print("Нет данных для анализа")
            return None
        
        # Для каждого направления делаем прогноз по трём сценариям
        results = {}
        
        for _, field in current_data.iterrows():
            field_results = {}
            for scenario in self.scenarios.keys():
                forecast = self.forecast_scenario(field, scenario, years_ahead)
                field_results[scenario] = forecast
            results[field['code']] = {
                'name': field['name'],
                'broad_group': field['broad_group'],
                'current_graduates': int(field['current_graduates']),
                'current_vacancies': int(field['current_vacancies']),
                'current_unemployed': int(field['current_unemployed']),
                'current_staff': int(field['current_staff']),
                'forecasts': field_results
            }
        
        return results
        
    def generate_scenario_report(self, results, report_type='study_field'):
        """
        Генерация текстового отчёта по сценариям
        """
        if not results:
            print("Нет данных для отчёта")
            return
        

        if report_type == 'study_field':   
            print("\n Прогноз баланса спроса и предложения по направлениям")

            print(f"{'Код':<10} {'Направление':<30} {'Текущие':<10} {'Пессим.':<10} {'Базовый':<10} {'Оптим.':<10} {'Разброс':<10}")

        
            for code, data in sorted(results.items(), key=lambda x: x[1]['current_vacancies'], reverse=True)[:15]:
                current = data['current_vacancies']
            
                p_balance = data['forecasts']['Пессимистичный'][-1]['balance'] if data['forecasts']['Пессимистичный'] else 0
                b_balance = data['forecasts']['Базовый'][-1]['balance'] if data['forecasts']['Базовый'] else 0
                o_balance = data['forecasts']['Оптимистичный'][-1]['balance'] if data['forecasts']['Оптимистичный'] else 0
            
                spread = o_balance - p_balance
            
                p_str = f"{p_balance:.0f}" if p_balance < 0 else f"{p_balance:.0f}"
                b_str = f" {b_balance:.0f}" if abs(b_balance) < 50 else (f" {b_balance:.0f}" if b_balance < 0 else f" {b_balance:.0f}")
                o_str = f" {o_balance:.0f}" if o_balance > 0 else f"{o_balance:.0f}"

                name = data['name'][:38] if len(data['name']) > 38 else data['name']
            
                print(f"{code:<10} {data['name'][:28]:<30} {current:<10} {p_str:<10} {b_str:<10} {o_str:<10} {spread:<10.0f}")
        else:
            print("\n Прогноз баланса спроса и предложения по профессиям")

            print(f"{'Профессия':<45} {'Текущие':>8} {'Пессим.':>10} {'Базовый':>10} {'Оптим.':>10} {'Разброс':>8}")
        
        
            for prof, data in sorted(results.items(), key=lambda x: x[1]['current_vacancies'], reverse=True)[:20]:
               current = data['current_vacancies']
            
               p_balance = data['forecasts']['Пессимистичный'][-1]['balance'] if data['forecasts']['Пессимистичный'] else 0
               b_balance = data['forecasts']['Базовый'][-1]['balance'] if data['forecasts']['Базовый'] else 0
               o_balance = data['forecasts']['Оптимистичный'][-1]['balance'] if data['forecasts']['Оптимистичный'] else 0
            
               spread = o_balance - p_balance
               name = prof[:43] if len(prof) > 43 else prof
            
               print(f"{name:<45} {current:>8} {p_balance:>10} {b_balance:>10} {o_balance:>10} {spread:>8}")

        return results
    
    def plot_scenario_comparison(self, results, fig, top_n=6,  selected_code=None):
        """
        Визуализация сценарного анализа с возможностью выбора специальности
        """
        if not results:
            print("Нет данных для визуализации")
            return
    
        first_item = next(iter(results.values()))
        is_profession = first_item.get('type') == 'profession'

        fig.clear()
        # Выбираем топ-N направлений по текущим вакансиям
        sorted_fields = sorted(results.items(), 
                               key=lambda x: x[1]['current_vacancies'], 
                               reverse=True)[:top_n]
    
        # Создаём словарь для выбора специальности

        scenarios = list(self.scenarios.keys())
        #scenarios = list(results.keys())
        
       # axes = fig.subplots(1, 5)
        #ax1, ax2, ax3, ax4, ax5 = axes.flatten()

        axes = fig.subplots(2, 3)
    
    # Получаем все подграфики в плоский список
        ax_list = axes.flatten()
    
    # Используем первые 5 подграфиков
        ax1, ax2, ax3, ax4, ax5 = ax_list[:5]
    
    # 6-й подграфик скрываем
        ax_list[5].set_visible(False)
      
        

        # 1. Сводная таблица дефицита по сценариям
        x = np.arange(len(scenarios))
        width = 0.25

        
       
        for i, (code, data) in enumerate(sorted_fields[:4]):
            balances = []
            for s in scenarios:
                forecast = data['forecasts'][s]
                if forecast:
                    balances.append(forecast[-1]['balance'])
                else:
                    balances.append(0)
        
            offset = (i - len(sorted_fields[:4])/2) * width

            if is_profession:
                label = data['name'][:20] + '...' if len(data['name']) > 20 else data['name']
            else:
                label = code

            ax1.bar(x + offset, balances, width, label=label, alpha=0.8)
    
        ax1.axhline(y=0, color='black', linewidth=2)
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenarios, fontsize=10)
        ax1.set_ylabel('Баланс (чел.)', fontsize=11)
        ax1.set_title('Прогноз баланса через 5 лет', fontsize=12)
        ax1.legend(loc='best', fontsize=8)
        ax1.grid(True, alpha=0.3)
    
        # 2-3. Динамика по выбранной специальности
        if selected_code and selected_code in results:
            selected_data = results[selected_code]
        
            # 2. Динамика по базовому сценарию
            #ax2 = fig.add_subplot(2, 3, 2)
            base_forecast = selected_data['forecasts']['Базовый']
            if base_forecast:
                years = [f['year'] for f in base_forecast]
                supply = [f['supply'] for f in base_forecast]
                demand = [f['demand'] for f in base_forecast]
            
                ax2.plot(years, supply, 'o-', label='Предложение', color='green', linewidth=2, markersize=8)
                ax2.plot(years, demand, 's-', label='Спрос', color='red', linewidth=2, markersize=8)
                ax2.fill_between(years, supply, demand, 
                                 where=(np.array(supply) < np.array(demand)),
                                 color='red', alpha=0.3, label='Дефицит')
                ax2.set_xlabel('Год', fontsize=11)
                ax2.set_ylabel('Количество', fontsize=11)
                if is_profession:
                    title_name = selected_data['name'][:16] + '...' if len(selected_data['name']) > 16 else selected_data['name']
                    ax2.set_title(f'Базовый сценарий: {title_name}', fontsize=13)
                else:
                    ax2.set_title(f'Базовый сценарий: {selected_code}', fontsize=13)
                ax2.legend(fontsize=8)
                ax2.grid(True, alpha=0.3)
                ax2.set_xticks(years)  
                ax2.set_xticklabels(years, rotation=45)
        
            # 3. Сравнение сценариев
            #ax3 = fig.add_subplot(2, 3, 3)
            colors = [self.scenarios[s]['color'] for s in scenarios]
        
            for s, color in zip(scenarios, colors):
                forecast = selected_data['forecasts'][s]
                if forecast:
                    years = [f['year'] for f in forecast]
                    balances = [f['balance'] for f in forecast]
                    ax3.plot(years, balances, 'o-', color=color, label=s, linewidth=2, markersize=6)
        
            ax3.axhline(y=0, color='black', linestyle='--', linewidth=1)
            ax3.set_xlabel('Год', fontsize=11)
            ax3.set_ylabel('Баланс (чел.)', fontsize=11)
            if is_profession:
                ax3.set_title(f'Сравнение сценариев', fontsize=13)
            else:
                ax3.set_title(f'Сравнение сценариев: {selected_code}', fontsize=13)
            ax3.legend(fontsize=8)
            ax3.grid(True, alpha=0.3)
            all_years = sorted(set([y for s in scenarios for y in [f['year'] for f in selected_data['forecasts'][s]]]))
            ax3.set_xticks(all_years)
            ax3.set_xticklabels(all_years, rotation=45)
        
        else:
            # Если специальность не выбрана, показываем топ-1
            #ax2 = fig.add_subplot(2, 3, 2)
            top_field = sorted_fields[0]
            code, data = top_field
        
            base_forecast = data['forecasts']['Базовый']
            if base_forecast:
                years = [f['year'] for f in base_forecast]
                supply = [f['supply'] for f in base_forecast]
                demand = [f['demand'] for f in base_forecast]
            
                ax2.plot(years, supply, 'o-', label='Предложение', color='green', linewidth=2, markersize=8)
                ax2.plot(years, demand, 's-', label='Спрос', color='red', linewidth=2, markersize=8)
                ax2.fill_between(years, supply, demand, 
                                 where=(np.array(supply) < np.array(demand)),
                                 color='red', alpha=0.3, label='Дефицит')
                ax2.set_xlabel('Год', fontsize=11)
                ax2.set_ylabel('Количество', fontsize=11)
                ax2.set_title(f'Базовый сценарий: {code} ', fontsize=13)
                ax2.legend(fontsize=8)
                ax2.grid(True, alpha=0.3)
                ax2.set_xticks(years)  
                ax2.set_xticklabels(years, rotation=45)
        
            #ax3 = fig.add_subplot(2, 3, 3)
            colors = [self.scenarios[s]['color'] for s in scenarios]
        
            for s, color in zip(scenarios, colors):
                forecast = data['forecasts'][s]
                if forecast:
                    years = [f['year'] for f in forecast]
                    balances = [f['balance'] for f in forecast]
                    ax3.plot(years, balances, 'o-', color=color, label=s, linewidth=2, markersize=6)
        
            ax3.axhline(y=0, color='black', linestyle='--', linewidth=1)
            ax3.set_xlabel('Год', fontsize=11)
            ax3.set_ylabel('Баланс (чел.)', fontsize=11)
            ax3.set_title(f'Сравнение сценариев: {code}', fontsize=13)
            ax3.legend(fontsize=8)
            ax3.grid(True, alpha=0.3)
            all_years = sorted(set([y for s in scenarios for y in [f['year'] for f in data['forecasts'][s]]]))
            ax3.set_xticks(all_years)
            ax3.set_xticklabels(all_years, rotation=45)
    
        
        # 4. Тепловая карта
        #ax4 = fig.add_subplot(2, 3, 4)
        deficit_matrix = []
        labels = []
    
        for code, data in sorted_fields[:6]:
            row = []
            for s in scenarios:
                forecast = data['forecasts'][s]
                if forecast:
                    balance = forecast[-1]['balance']
                    row.append(balance)
                else:
                    row.append(0)
            deficit_matrix.append(row)
            labels.append(code)
    
        im = ax4.imshow(deficit_matrix, cmap='RdYlGn_r', aspect='auto')
        ax4.set_xticks(range(len(scenarios)))
        ax4.set_xticklabels(scenarios,  fontsize=9)
        ax4.set_yticks(range(len(labels)))
        ax4.set_yticklabels(labels, fontsize=9)
        ax4.set_title('Тепловая карта дефицита через 5 лет', fontsize=12)
    
        for i in range(len(labels)):
            for j in range(len(scenarios)):
                val = deficit_matrix[i][j]
                color = 'white' if abs(val) < 50 else 'black'
                ax4.text(j, i, f'{val:.0f}', ha='center', va='center', color=color, fontsize=8)
    
        plt.colorbar(im, ax=ax4, label='Баланс (чел.)')
    
        # 5. Текущее состояние
        #ax5 = fig.add_subplot(2, 3, 5)
        codes = [code for code, _ in sorted_fields[:8]]
        vacancies = [data['current_vacancies'] for _, data in sorted_fields[:8]]
        graduates = [data['current_graduates'] for _, data in sorted_fields[:8]]
    
        x = np.arange(len(codes))
        width = 0.35
    
        ax5.bar(x - width/2, vacancies, width, label='Вакансии', color='#FF6B6B')
        ax5.bar(x + width/2, graduates, width, label='Выпускники', color='#45B7D1')
        ax5.set_xticks(x)
        ax5.set_xticklabels(codes, rotation=45, ha='right', fontsize=8)
        ax5.set_ylabel('Количество', fontsize=11)
        ax5.set_title('Текущее состояние', fontsize=12)
        ax5.legend(fontsize=8)
    
        
        fig.tight_layout()

        cursor1 = mplcursors.cursor(ax2, hover=True)
        cursor1.connect("add", lambda sel: sel.annotation.set_text(
            f"Год: {int(sel.target[0])}\n"
            f"{sel.artist.get_label()}: {int(sel.target[1])}"
        ))

        # Для графика баланса (столбцы)
        cursor2 = mplcursors.cursor(ax1, hover=True)
        cursor2.connect("add", lambda sel: sel.annotation.set_text(
            f"{sel.artist.get_label()}\n"
            f"Баланс: {int(sel.target[1])}"
))
    


