"""
Анализатор по профессиям: спрос, предложение, конкуренция
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CompetitionLevel(Enum):
    """Уровень конкуренции за место"""
    EXTREME = "Экстремальная"      # >50 кандидатов на место
    HIGH = "Высокая"                # 10-50 кандидатов
    MEDIUM = "Средняя"              # 3-10 кандидатов
    LOW = "Низкая"                  # 1-3 кандидата
    SHORTAGE = "Дефицит"            # <1 кандидата на место


@dataclass
class ProfessionAnalysis:
    """Результат анализа по профессии"""
    profession: str
    category: str
    is_itr: bool
    
    # Спрос
    current_staff: int              # Сколько работает
    open_vacancies: int             # Открытых вакансий
    total_demand: int               # Общий спрос
    
    # Предложение
    unemployed: int                 # Безработных на учете
    annual_graduates: int           # Выпускников в год
    total_supply: int               # Общее предложение
    
    # Показатели
    candidates_per_vacancy: float   # Кандидатов на одну вакансию
    coverage_ratio: float           # Покрытие спроса предложением
    competition_level: str          # Уровень конкуренции
    
    # Зарплаты
    salary_min: int
    salary_max: int
    salary_avg: int
    
    # Рекомендации
    recommendations: List[str]


class ProfessionAnalyser:
    """
    Анализатор по профессиям
    
       """
    
    def __init__(self, conn_string: str):
        self.engine = create_engine(conn_string)
    
    def _get_session(self):
        return self.engine.connect()
    
    def _get_competition_level(self, candidates_per_vacancy: float) -> str:
        """Определяет уровень конкуренции"""
        if pd.isna(candidates_per_vacancy) or candidates_per_vacancy == float('inf'):
            return CompetitionLevel.SHORTAGE.value
        elif candidates_per_vacancy >= 50:
            return CompetitionLevel.EXTREME.value
        elif candidates_per_vacancy >= 10:
            return CompetitionLevel.HIGH.value
        elif candidates_per_vacancy >= 3:
            return CompetitionLevel.MEDIUM.value
        elif candidates_per_vacancy >= 1:
            return CompetitionLevel.LOW.value
        else:
            return CompetitionLevel.SHORTAGE.value
    
    def _generate_profession_recommendations(self, profession: str, 
                                               candidates_per_vacancy: float,
                                               coverage_ratio: float,
                                               open_vacancies: int) -> List[str]:
        """Генерирует рекомендации по профессии"""
        recommendations = []
        
        # Дефицит
        if candidates_per_vacancy < 1:
            recommendations.append(f"Критический дефицит: {open_vacancies} открытых вакансий")
            recommendations.append("Рекомендуется повышение зарплаты на 20-30%")
            recommendations.append(" Увеличить целевой набор студентов")
            recommendations.append("Рассмотреть возможность привлечения специалистов из других регионов")
        
        elif candidates_per_vacancy < 3:
            recommendations.append(f"Умеренный дефицит: {candidates_per_vacancy:.1f} кандидатов на место")
            recommendations.append("Повышение зарплаты на 10-15%")
            recommendations.append("Развивать программу стажировок")
        
        elif candidates_per_vacancy < 10:
            recommendations.append(f"Сбалансировано: {candidates_per_vacancy:.1f} кандидатов на место")
            recommendations.append("Продолжить текущую кадровую политику")
        
        elif candidates_per_vacancy < 50:
            recommendations.append(f"Высокая конкуренция: {candidates_per_vacancy:.1f} кандидатов на место")
            recommendations.append("Ужесточить требования к кандидатам")
            recommendations.append("Оптимизировать процесс отбора")
        
        else:
            recommendations.append(f"Экстремальная конкуренция: {candidates_per_vacancy:.0f} кандидатов на место")
            recommendations.append("Рынок перенасыщен, возможно снижение зарплат")
            recommendations.append("Рассмотреть смежные профессии для трудоустройства")
        
        # Покрытие спроса
        if coverage_ratio < 0.5:
            recommendations.append("Спрос превышает предложение более чем в 2 раза")
        elif coverage_ratio > 1.5:
            recommendations.append("Предложение превышает спрос, возможна конкуренция")
        
        return recommendations
    
    def analyze_profession(self, profession_name: str) -> ProfessionAnalysis:
        """
        Детальный анализ конкретной профессии
        
        """
        with self._get_session() as conn:
            # Поиск профессии
            pos_query = text("""
                SELECT 
                    p.id, 
                    p.name, 
                    p.category, 
                    p.is_itr,
                    COALESCE(lb.active_vacancies, 0) as open_vacancies,
                    COALESCE(lb.unemployed_count, 0) as unemployed,
                    COALESCE(lb.salary_min, 0) as salary_min,
                    COALESCE(lb.salary_max, 0) as salary_max,
                    COALESCE((
                        SELECT SUM(sf.staff_count) 
                        FROM staff_fact sf 
                        WHERE sf.position_id = p.id
                    ), 0) as current_staff
                FROM positions p
                LEFT JOIN labor_market_balance lb ON p.id = lb.position_id
                WHERE p.name ILIKE :name
                LIMIT 1
            """)
        
            result = conn.execute(pos_query, {"name": f"%{profession_name}%"})
            row = result.fetchone()
        
            if not row:
                raise ValueError(f"Профессия '{profession_name}' не найдена")
        
            position_id = row[0]
            position_name = row[1]
            category = row[2]
            is_itr = row[3]
            open_vacancies = row[4]
            unemployed = row[5]
            salary_min = row[6]
            salary_max = row[7]
            current_staff = row[8]
        
            employment_rate = 0.30# сколько еще не устроено по статистике  
            profile_match = 0.55# сколько работают по специальности
            effective_rate = employment_rate * profile_match

            # Выпускники (только если есть связь, иначе 0)
            grad_query = text("""
               SELECT COALESCE(ROUND(SUM(g.graduates_total) * :effective_rate), 0) as graduates
        FROM position_study_field psf
        JOIN graduations g ON psf.study_field_id = g.study_field_id
        WHERE psf.position_id = :position_id
            AND g.year >= EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 1
            """)
            grad_result = conn.execute(grad_query, {"position_id": position_id, "effective_rate": effective_rate})
            annual_graduates = grad_result.fetchone()[0]

            unemployed_relevance = 0.7
            unemployed = int(unemployed * unemployed_relevance)

    
        total_demand = current_staff + open_vacancies
        total_supply = unemployed + annual_graduates
    
        if open_vacancies > 0:
            candidates_per_vacancy = round(total_supply / open_vacancies, 2)
        else:
            candidates_per_vacancy = float('inf')
    
        if total_demand > 0:
            coverage_ratio = round(total_supply / total_demand, 2)
        else:
            coverage_ratio = 0
    
        salary_avg = (salary_min + salary_max) // 2 if salary_max > 0 else salary_min
    
        recommendations = self._generate_profession_recommendations(
            position_name, candidates_per_vacancy, coverage_ratio, open_vacancies
        )
    
        return ProfessionAnalysis(
            profession=position_name,
            category=category or 'не определена',
            is_itr=is_itr or False,
            current_staff=int(current_staff),
            open_vacancies=int(open_vacancies),
            total_demand=int(total_demand),
            unemployed=int(unemployed),
            annual_graduates=int(annual_graduates),
            total_supply=int(total_supply),
            candidates_per_vacancy=candidates_per_vacancy if candidates_per_vacancy != float('inf') else float('inf'),
            coverage_ratio=coverage_ratio,
            competition_level=self._get_competition_level(candidates_per_vacancy),
            salary_min=int(salary_min),
            salary_max=int(salary_max),
            salary_avg=int(salary_avg),
            recommendations=recommendations
        )
    
    def analyze_all_professions(self, min_staff = 0) -> pd.DataFrame:
        """
        Анализирует все профессии
        
        """
        with self._get_session() as conn:
            employment_rate=0.30
            profile_match=0.55
            unemployed_relevance=0.7
            migration = 0.8
            effective_graduate_rate = employment_rate * profile_match * migration

            query = text("""
                WITH 
            staff_stats AS (
                SELECT 
                    p.id as position_id,
                    p.name as profession,
                    p.category,
                    p.is_itr,
                    COALESCE(SUM(sf.staff_count), 0) as current_staff
                FROM positions p
                LEFT JOIN staff_fact sf ON p.id = sf.position_id
                GROUP BY p.id, p.name, p.category, p.is_itr
            ),
            vacancy_stats AS (
                SELECT 
                    p.id as position_id,
                    COALESCE(SUM(v.vacancies_count), 0) as open_vacancies,
                    COALESCE(AVG(v.salary_min), 0) as avg_salary_min,
                    COALESCE(AVG(v.salary_max), 0) as avg_salary_max
                FROM vacancies v
                JOIN positions p ON v.position_id = p.id
                WHERE v.relevance_date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY p.id
            ),
            unemployed_stats AS (
                SELECT 
                    position_id,
                    COALESCE(SUM(unemployed_count) * :unemployed_relevance, 0) as unemployed
                FROM labor_market_balance
                WHERE data_period >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY position_id
            ),
            graduate_stats AS (
                SELECT 
                    psf.position_id,
                    COALESCE(ROUND(SUM(g.graduates_total) * :effective_graduate_rate), 0) as annual_graduates
                FROM position_study_field psf
                JOIN graduations g ON psf.study_field_id = g.study_field_id
                WHERE g.year >= EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 1
                GROUP BY psf.position_id
            )
            SELECT 
                ss.profession,
                ss.category,
                ss.is_itr,
                ss.current_staff,
                COALESCE(vs.open_vacancies, 0) as open_vacancies,
                COALESCE(us.unemployed, 0) as unemployed,
                COALESCE(gs.annual_graduates, 0) as annual_graduates,
                COALESCE(vs.avg_salary_min, 0) as salary_min,
                COALESCE(vs.avg_salary_max, 0) as salary_max
            FROM staff_stats ss
            LEFT JOIN vacancy_stats vs ON ss.position_id = vs.position_id
            LEFT JOIN unemployed_stats us ON ss.position_id = us.position_id
            LEFT JOIN graduate_stats gs ON ss.position_id = gs.position_id
            WHERE ss.current_staff >= :min_staff OR COALESCE(vs.open_vacancies, 0) > 0
            ORDER BY ss.current_staff + COALESCE(vs.open_vacancies, 0) DESC
        """)
            
            df = pd.read_sql(query, conn, params={
                "min_staff": min_staff,
                "effective_graduate_rate": effective_graduate_rate,
                "unemployed_relevance": unemployed_relevance
            })
    
        if df.empty:
            return df
    
        df['total_demand'] = df['current_staff'] + df['open_vacancies']
        df['total_supply'] = df['unemployed'] + df['annual_graduates']
    
        df['candidates_per_vacancy'] = df.apply(
            lambda x: round(x['total_supply'] / x['open_vacancies'], 2) 
            if x['open_vacancies'] > 0 else float('inf'), 
            axis=1
        )
    
        df['coverage_ratio'] = df.apply(
            lambda x: round(x['total_supply'] / x['total_demand'], 2) 
            if x['total_demand'] > 0 else 0,
            axis=1
        )
    
        df['salary_avg'] = df.apply(
            lambda x: (x['salary_min'] + x['salary_max']) // 2 
            if x['salary_max'] > 0 else x['salary_min'],
            axis=1
        )
    
        df['competition_level'] = df['candidates_per_vacancy'].apply(
            self._get_competition_level
        )
    
        df['deficit_status'] = df['coverage_ratio'].apply(
            lambda x: 'Дефицит' if x < 0.8 else ('Профицит' if x > 1.2 else 'Сбалансирован')
        )
    
        return df
    
    def get_top_deficit_professions(self, limit = 10, only_itr = False) -> pd.DataFrame:
        """
        Получает топ профессий с наибольшим дефицитом
        
        """
        
        
        query = text('''
        SELECT 
            p.name AS profession,
            p.category,
            p.is_itr,
            lb.active_vacancies AS open_vacancies,
            COALESCE(lb.unemployed_count, 0) AS unemployed,
            ROUND(COALESCE(lb.unemployed_count, 0)::numeric / NULLIF(lb.active_vacancies, 0), 2) AS candidates_per_vacancy,
            (lb.salary_min + lb.salary_max) / 2 AS salary_avg,
            lb.data_period,
            COALESCE((
                SELECT SUM(sf.staff_count) 
                FROM staff_fact sf 
                WHERE sf.position_id = p.id
            ), 0) AS current_staff,
            COALESCE((
                SELECT SUM(g.graduates_total)
                FROM position_study_field psf
                JOIN graduations g ON psf.study_field_id = g.study_field_id
                WHERE psf.position_id = p.id
                AND g.year >= EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 1
            ), 0) AS annual_graduates
        FROM labor_market_balance lb
        JOIN positions p ON lb.position_id = p.id
        WHERE lb.active_vacancies > 0
        ''')

        with self._get_session() as conn:
            df = pd.read_sql(query, conn)

        if df.empty:
            return df

        if only_itr:
            df = df[df['is_itr'] == True]

        deficit_df = df[df['candidates_per_vacancy'] < 1].copy()
    
        if deficit_df.empty:
            return deficit_df
        

        deficit_df = deficit_df.sort_values('candidates_per_vacancy', ascending=True)
    
        # приоритет: чем больше вакансий и меньше кандидатов, тем выше
        deficit_df['priority'] = deficit_df['open_vacancies'] * (1 - deficit_df['candidates_per_vacancy'])
    
        return deficit_df.head(limit)[[
            'profession', 'category', 'open_vacancies', 'current_staff',
            'unemployed', 'annual_graduates', 'candidates_per_vacancy',
            'salary_avg', 'priority'
        ]]
    
    def get_top_surplus_professions(self, limit = 10, only_itr = False) -> pd.DataFrame:
        """
        Получает топ профессий с наибольшим профицитом
        """
        query = text('''
        SELECT 
            p.name AS profession,
            p.category,
            p.is_itr,
            lb.active_vacancies AS open_vacancies,
            COALESCE(lb.unemployed_count, 0) AS unemployed,
            ROUND(COALESCE(lb.unemployed_count, 0)::numeric / NULLIF(lb.active_vacancies, 0), 2) AS candidates_per_vacancy,
            (lb.salary_min + lb.salary_max) / 2 AS salary_avg,
            lb.data_period
        FROM labor_market_balance lb
        JOIN positions p ON lb.position_id = p.id
        WHERE lb.active_vacancies > 0
    ''')
         
        with self._get_session() as conn:
            df = pd.read_sql(query, conn)
    
        if df.empty:
            return df
    
        
        if only_itr:
            df = df[df['is_itr'] == True]
    
       
        surplus_df = df[df['candidates_per_vacancy'] > 3].copy()
    
        if surplus_df.empty:
            return surplus_df
    
        surplus_df = surplus_df.sort_values('candidates_per_vacancy', ascending=False)

        surplus_df['current_staff'] = 0
        surplus_df['annual_graduates'] = 0
    
        return surplus_df.head(limit)[[
            'profession', 'category', 'open_vacancies', 'current_staff',
            'unemployed', 'annual_graduates', 'candidates_per_vacancy',
            'salary_avg'
        ]]
    
    def get_profession_comparison(self, professions: List[str]) -> pd.DataFrame:
        """
        Сравнивает несколько профессий
                """

        if not professions:
            return pd.DataFrame()

        conditions = ' OR '.join([f"p.name ILIKE '%{prof}%'" for prof in professions])
    
        query = text(f'''
            SELECT 
                p.name AS profession,
                p.category,
                p.is_itr,
                COALESCE(lb.active_vacancies, 0) AS vacancies,
                COALESCE(lb.unemployed_count, 0) AS unemployed,
                COALESCE(lb.salary_min, 0) AS salary_min,
                COALESCE(lb.salary_max, 0) AS salary_max,
                CASE 
                    WHEN lb.active_vacancies IS NULL OR lb.active_vacancies = 0 THEN NULL
                    ELSE ROUND(lb.unemployed_count::numeric / lb.active_vacancies, 2)
                END AS candidates_per_vacancy,
                CASE 
                    WHEN lb.id IS NULL THEN 'Нет данных'
                    WHEN lb.active_vacancies = 0 THEN 'Нет вакансий'
                    WHEN lb.unemployed_count < lb.active_vacancies THEN 'Дефицит'
                    WHEN lb.unemployed_count > lb.active_vacancies THEN 'Профицит'
                    ELSE 'Сбалансировано'
                END AS market_status
            FROM positions p
            LEFT JOIN labor_market_balance lb ON p.id = lb.position_id
            WHERE {conditions}
            ORDER BY p.name
        ''')
    
        with self._get_session() as conn:
            df = pd.read_sql(query, conn)
    
        results = []
    
        for prof in professions:
          
            found = df[df['profession'].str.lower() == prof.lower()]
        
            if found.empty:
                found = df[df['profession'].str.contains(prof, case=False, na=False)]
        
            if not found.empty:
                row = found.iloc[0]
            
                #  средняя зарплата
                if row['salary_max'] > 0:
                    salary_avg = (row['salary_min'] + row['salary_max']) // 2
                elif row['salary_min'] > 0:
                    salary_avg = row['salary_min']
                else:
                    salary_avg = 0
            
                #  кандидат на место
                if row['candidates_per_vacancy'] is None:
                    candidates_display = 'нет данных'
                elif row['candidates_per_vacancy'] == float('inf'):
                    candidates_display = 'нет вакансий'
                else:
                    candidates_display = row['candidates_per_vacancy']
            
                results.append({
                    'Профессия': row['profession'],
                    'Вакансий': int(row['vacancies']),
                    'Безработных': int(row['unemployed']),
                    'Кандидатов/место': candidates_display,
                    'Зарплата': salary_avg,
                    'Статус': row['market_status']
                })
            else:
                results.append({
                    'Профессия': prof,
                    'Вакансий': 0,
                    'Безработных': 0,
                    'Кандидатов/место': 'нет данных',
                    'Зарплата': 0,
                    'Статус': 'Профессия не найдена'
                })
    
        return pd.DataFrame(results)

    def generate_report(self, only_itr = False) -> str:
        """
        Генерирует текстовый отчет о рынке труда по профессиям
        """
        df = self.analyze_all_professions()

        if only_itr:
            df = df[df['is_itr'] == True]
        
        report = []
        
        report.append("Анализ рынка труда")
        #report.append(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
       
        
        if df.empty:
            report.append("\nНет данных для анализа")
            return "\n".join(report)
        
        # Общая статистика
        total_demand = df['total_demand'].sum()
        total_supply = df['total_supply'].sum()
        total_vacancies = df['open_vacancies'].sum()
        
        report.append("\nОбщая статистика:")
        #report.append(f"   • Всего профессий в анализе: {len(df)}")
        report.append(f"Общий спрос (штат + вакансии): {total_demand:,} чел.")
        report.append(f"Общее предложение: {total_supply:,} чел.")
        report.append(f"Открытых вакансий: {total_vacancies:,}")
        if total_vacancies > 0:
            report.append(f"В среднем кандидатов на место: {total_supply/total_vacancies:.2f}")
        
        # Дефицитные профессии
        report.append("\nТоп-10 дефицитные профессии:")
        deficit = self.get_top_deficit_professions(limit=10)
        if not deficit.empty:
            for _, row in deficit.iterrows():
                report.append(f" {row['profession']}: {row['open_vacancies']} вакансий, "
                            f"{row['candidates_per_vacancy']:.2f} чел./место")
        else:
            report.append("Дефицитных профессий не обнаружено")
        
        # Профицитные профессии
        report.append("\nТоп-10 профицитных профессий:")
        surplus = self.get_top_surplus_professions(10)
        if not surplus.empty:
            for _, row in surplus.iterrows():
                report.append(f" {row['profession']}: {row['open_vacancies']} вакансий, "
                            f"{row['candidates_per_vacancy']:.0f} чел./место")
        else:
            report.append("Профицитных профессий не обнаружено")   
        
        return "\n".join(report)


    
    def export_to_excel(self, filename: str = 'profession_analysis.xlsx'):
        """
        Экспортирует все анализы в Excel
        """
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Все профессии
            df_all = self.analyze_all_professions()
            df_all.to_excel(writer, sheet_name='Все_профессии', index=False)
            
            # Дефицитные
            deficit = self.get_top_deficit_professions(50)
            deficit.to_excel(writer, sheet_name='Дефицитные_профессии', index=False)
            
            # Профицитные
            surplus = self.get_top_surplus_professions(50)
            surplus.to_excel(writer, sheet_name='Профицитные_профессии', index=False)
            
            # Сводка по категориям
            if not df_all.empty:
                category_summary = df_all.groupby('category').agg({
                    'profession': 'count',
                    'total_demand': 'sum',
                    'open_vacancies': 'sum',
                    'candidates_per_vacancy': 'mean',
                    'salary_avg': 'mean'
                }).round(2)
                category_summary.columns = ['Кол-во_профессий', 'Всего_спрос', 'Вакансий', 
                                            'Кандидатов_на_место', 'Ср_зарплата']
                category_summary.to_excel(writer, sheet_name='Сводка_по_категориям')
        
        logger.info(f"Экспортировано в {filename}")

