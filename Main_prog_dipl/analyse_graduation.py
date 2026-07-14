"""
Анализатор потоков образования
"""

import psycopg2
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging
import warnings
import configparser
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EducationFlowAnalyser:
    """Анализатор потоков образования: прием и выпуск"""
    
    config = configparser.ConfigParser()
    config.read('data.ini')
    def __init__(self, host=config['Database']['host'], database=config['Database']['dbname'],
                 user=config['Database']['user'], password=config['Database']['password'], port=config['Database'].getint('port')):
        self.conn_params = {
            'host': host,
            'database': database,
            'user': user,
            'password': password,
            'port': port
        }
        self._conn = None
        self._region_id = None
    
    def connect(self):
        self._conn = psycopg2.connect(**self.conn_params)
        #logger.info("Подключено к PostgreSQL")
        return self
    
    def disconnect(self):
        if self._conn:
            self._conn.close()
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, *args):
        self.disconnect()
    
    def _get_region_id(self) -> int:
        if self._region_id:
            return self._region_id
        
        with self._conn.cursor() as cur:
            cur.execute("SELECT id FROM regions WHERE name = 'Курская область'")
            r = cur.fetchone()
            if r:
                self._region_id = r[0]
                return self._region_id
        return 1 
    
    def get_admissions_by_year(self, years: List[int] = None) -> pd.DataFrame:
        """Получает данные о приеме по годам и специальностям"""
        region_id = self._get_region_id()
        
        query = """
        SELECT 
            sf.code,
            sf.name,
            sf.broad_group,
            sf.is_itr,
            a.year,
            el.name as education_level,
            a.admitted_total,
            a.admitted_budget,
            a.admitted_paid,
            a.admitted_women
        FROM admissions a
        JOIN study_fields sf ON a.study_field_id = sf.id
        JOIN education_levels el ON a.education_level_id = el.id
        WHERE a.region_id = %s
        """
        
        if years:
            placeholders = ','.join(['%s'] * len(years))
            query += f" AND a.year IN ({placeholders})"
            params = [region_id] + years
        else:
            params = [region_id]
        
        query += " ORDER BY a.year DESC, sf.code"
        
        return pd.read_sql_query(query, self._conn, params=params)
    
    def get_graduations_by_year(self, years: List[int] = None) -> pd.DataFrame:
        """Получает данные о выпуске по годам и специальностям"""
        region_id = self._get_region_id()
        
        query = """
        SELECT 
            sf.code,
            sf.name,
            sf.broad_group,
            sf.is_itr,
            g.year,
            el.name as education_level,
            g.graduates_total,
            g.graduates_budget,
            g.graduates_paid,
            g.graduates_women
        FROM graduations g
        JOIN study_fields sf ON g.study_field_id = sf.id
        JOIN education_levels el ON g.education_level_id = el.id
        WHERE g.region_id = %s
        """
        
        if years:
            placeholders = ','.join(['%s'] * len(years))
            query += f" AND g.year IN ({placeholders})"
            params = [region_id] + years
        else:
            params = [region_id]
        
        query += " ORDER BY g.year DESC, sf.code"
        
        return pd.read_sql_query(query, self._conn, params=params)
    
    def compare_admission_graduation(self, start_year: int = 2020, end_year: int = 2025) -> pd.DataFrame:
        """
        Сравнивает прием и выпуск с учетом сдвига по годам обучения
        """
        # Получаем все специальности и уровни образования
        query = """
         WITH level_duration AS (
        SELECT id, name, 
               CASE 
                   WHEN name = 'Бакалавриат' THEN 4
                   WHEN name = 'Специалитет' THEN 5
                   WHEN name = 'Магистратура' THEN 2
                   ELSE 4
               END as duration
        FROM education_levels
        )
        SELECT 
            sf.code,
            sf.name,
            sf.broad_group,
            sf.is_itr,
            ld.name as education_level,
            a.year as admission_year,
            a.admitted_total,
            a.admitted_budget,
            a.admitted_paid,
            a.admitted_women,
            (a.year + ld.duration) as graduation_year,
            COALESCE(g.graduates_total, 0) as graduates_total,
            COALESCE(g.graduates_budget, 0) as graduates_budget,
            COALESCE(g.graduates_paid, 0) as graduates_paid,
            COALESCE(g.graduates_women, 0) as graduates_women
        FROM admissions a
        JOIN study_fields sf ON sf.id = a.study_field_id
        JOIN level_duration ld ON ld.id = a.education_level_id
        LEFT JOIN graduations g ON 
            g.study_field_id = a.study_field_id 
            AND g.education_level_id = a.education_level_id
            AND g.year = a.year + ld.duration
            AND g.region_id = %s
        WHERE a.region_id = %s
            AND a.year BETWEEN %s AND %s
    """
    
        region_id = self._get_region_id()
        df = pd.read_sql_query(query, self._conn, params=(region_id, region_id, start_year, end_year))
    
        if df.empty:
             return pd.DataFrame()
    
    # Добавляем расчетные поля
        df['retention_rate'] = df.apply(
            lambda row: round(row['graduates_total'] / row['admitted_total'], 3) 
            if row['admitted_total'] > 0 else 0, axis=1
        )
        df['loss'] = df['admitted_total'] - df['graduates_total']
    
        return df
    
    def get_detailed_analysis(self, year: int, education_level: str = None) -> pd.DataFrame:
        """Детальный анализ для конкретного года """
        region_id = self._get_region_id()
        
        
        query = """
        SELECT 
            sf.code,
            sf.name,
            sf.broad_group,
            sf.is_itr,
            el.name as education_level,
            COALESCE(a.admitted_total, 0) as admitted_total,
            COALESCE(a.admitted_budget, 0) as admitted_budget,
            COALESCE(a.admitted_paid, 0) as admitted_paid,
            COALESCE(a.admitted_women, 0) as admitted_women,
            COALESCE(g.graduates_total, 0) as graduates_total,
            COALESCE(g.graduates_budget, 0) as graduates_budget,
            COALESCE(g.graduates_paid, 0) as graduates_paid,
            COALESCE(g.graduates_women, 0) as graduates_women,
            COALESCE(e.students_total, 0) as first_year_students,
            COALESCE(e.students_budget, 0) as first_year_budget,
            COALESCE(e.students_paid, 0) as first_year_paid,
            CASE 
                WHEN COALESCE(a.admitted_total, 0) > 0 THEN 
                    ROUND(COALESCE(g.graduates_total, 0)::numeric / a.admitted_total, 3)
                ELSE 0
            END as retention_rate
        FROM study_fields sf
        LEFT JOIN admissions a ON a.study_field_id = sf.id 
            AND a.region_id = %s 
            AND a.year = %s
        LEFT JOIN graduations g ON g.study_field_id = sf.id 
            AND g.region_id = %s 
            AND g.year = %s
        LEFT JOIN enrollments e ON e.study_field_id = sf.id 
            AND e.region_id = %s 
            AND e.year = %s 
            AND e.course = 1
        LEFT JOIN education_levels el ON 
            (a.education_level_id = el.id OR g.education_level_id = el.id OR e.education_level_id = el.id)
        WHERE sf.code IS NOT NULL
        """
        
        params = [region_id, year, region_id, year, region_id, year]
        
        
        if education_level:
            query += " AND el.name = %s"
            params.append(education_level)
        
        query += " GROUP BY sf.code, sf.name, sf.broad_group, sf.is_itr, el.name, a.admitted_total, a.admitted_budget, a.admitted_paid, a.admitted_women, g.graduates_total, g.graduates_budget, g.graduates_paid, g.graduates_women, e.students_total, e.students_budget, e.students_paid"
        query += " ORDER BY sf.code"
        
        try:
            df = pd.read_sql_query(query, self._conn, params=params)
            return df
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
          
            simple_query = """
            SELECT 
                sf.code,
                sf.name,
                sf.broad_group,
                sf.is_itr,
                a.year,
                a.admitted_total,
                a.admitted_budget,
                a.admitted_paid,
                a.admitted_women,
                g.graduates_total,
                g.graduates_budget,
                g.graduates_paid,
                g.graduates_women
            FROM study_fields sf
            LEFT JOIN admissions a ON a.study_field_id = sf.id AND a.region_id = %s AND a.year = %s
            LEFT JOIN graduations g ON g.study_field_id = sf.id AND g.region_id = %s AND g.year = %s
            WHERE sf.code IS NOT NULL
            ORDER BY sf.code
            """
            simple_params = [region_id, year, region_id, year]
            return pd.read_sql_query(simple_query, self._conn, params=simple_params)
    
    def get_summary_statistics(self, years: List[int]) -> Dict:
     """Получает сводную статистику по годам (динамика приёма)"""
     region_id = self._get_region_id()
    
    # Данные по приёму
     adm_query = """
    SELECT year, SUM(admitted_total) as total_admitted
    FROM admissions
    WHERE region_id = %s AND year = ANY(%s)
    GROUP BY year
    ORDER BY year
    """
    
    # Данные по выпуску
     grad_query = """
    SELECT year, SUM(graduates_total) as total_graduates
    FROM graduations
    WHERE region_id = %s AND year = ANY(%s)
    GROUP BY year
    ORDER BY year
    """

     itr_adm_query = """
    SELECT a.year, SUM(a.admitted_total) as itr_admitted
    FROM admissions a
    JOIN study_fields sf ON a.study_field_id = sf.id
    WHERE a.region_id = %s AND a.year = ANY(%s) AND sf.is_itr = TRUE
    GROUP BY a.year
    ORDER BY a.year
    """
    
     adm_df = pd.read_sql_query(adm_query, self._conn, params=(region_id, years))
     grad_df = pd.read_sql_query(grad_query, self._conn, params=(region_id, years))
     itr_adm_df = pd.read_sql_query(itr_adm_query, self._conn, params=(region_id, years))
    
     stats_by_year = {}
     prev_adm = None
    
     for year in years:
         adm = adm_df[adm_df['year'] == year]['total_admitted'].iloc[0] if not adm_df[adm_df['year'] == year].empty else 0
         grad = grad_df[grad_df['year'] == year]['total_graduates'].iloc[0] if not grad_df[grad_df['year'] == year].empty else 0
         itr_adm = itr_adm_df[itr_adm_df['year'] == year]['itr_admitted'].iloc[0] if not itr_adm_df[itr_adm_df['year'] == year].empty else 0
        
        # Динамика приёма
         if prev_adm is not None and prev_adm > 0:
             adm_growth = round((adm - prev_adm) / prev_adm * 100, 1)
         else:
             adm_growth = 0
        
         stats_by_year[year] = {
            'total_admitted': int(adm),
            'total_graduates': int(grad),
            'itr_admitted': int(itr_adm),
            'admission_growth': adm_growth,  # динамика приёма
            'gap': int(adm - grad)  # разрыв между приёмом и выпуском
        }
        
         prev_adm = adm
    
     return stats_by_year
    
    def generate_report(self, years: List[int]) -> Dict:
        """Генерация полного отчет"""
        logger.info(f"Генерация отчета за {years}")
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'years': years,
            'statistics': self.get_summary_statistics(years)
        }
               
        self._print_report(report)
        return report
    
    def _print_report(self, report: Dict):
        """Вывод отчета в консоль"""
      
        print("Отчет по сравнению приема и выпуска ")
        print("\nСводная статистика по годам:")
     
        print(f"{'Год':<6} {'Принято':>10} {'Выпущено':>10} {'Динамика приёма':>16} {'Доля ИТР':>12} {'Разрыв':>10}")
       
    
        prev_adm = None
        for year, stats in report['statistics'].items():
         if stats:
             itr_share = round(stats['itr_admitted'] / stats['total_admitted'] * 100, 1) if stats['total_admitted'] > 0 else 0
             growth_str = f"{stats['admission_growth']:>14.1f}%" if stats['admission_growth'] != 0 else "         базовый"
            
             print(f"{year:<6} {stats['total_admitted']:>10,} "
                  f"{stats['total_graduates']:>10,} "
                  f"{growth_str:>16} "
                  f"{itr_share:>11.1f}% "
                  f"{stats['gap']:>9,}")
    
    
    def print_detailed_by_year(self, year: int, top_n: int = 15, only_itr: bool = False):
     """
     Вывод детал анализа за указанный год
    
    Parameters:
    year : int Год для анализа
    top_n : int  Количество выводимых записей
    only_itr : bool  Только ИТР-направления (True) или все (False)
     """
     df = self.get_detailed_analysis(year)
    
     if df.empty:
         print(f"Нет данных за {year} год")
         return
    
    # Фильтрация по ИТР
     if only_itr and 'is_itr' in df.columns:
         df = df[df['is_itr'] == True]
    
     if df.empty:
        print(f"Нет ИТР-направлений за {year} год")
        return
    
    # Заголовок
     itr_text = " (только ИТР)" if only_itr else ""
     print(f"\nДеталиный анализ за {year} год{itr_text}")
     print(f"{'Код':<10} {'Название':<40} {'Принято':>8} {'Выпущено':>8} {'Разрыв':>8}")
    
     for _, row in df.head(top_n).iterrows():
          name = row['name'][:38] if len(str(row['name'])) > 38 else row['name']
          gap = row['admitted_total'] - row['graduates_total']
        
          print(f"{row['code']:<10} {name:<40} {row['admitted_total']:>8,} {row['graduates_total']:>8,} {gap:>8,}")
    
    def export_to_excel(self, years: List[int], filename: str = None):
        """Экспортирует данные в Excel"""
        if filename is None:
            filename = f"education_flow_{min(years)}_{max(years)}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            for year in years:
                detailed = self.get_detailed_analysis(year)
                if not detailed.empty:
                    sheet_name = f'Детально_{year}'
                    detailed.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            
            # Сравнение приема и выпуска
            comparison = self.compare_admission_graduation(min(years), max(years))
            if not comparison.empty:
                comparison.to_excel(writer, sheet_name='Сравнение', index=False)
        
        logger.info(f"Отчет сохранен в {filename}")
        return filename

    
    def forecast_graduates_by_year(self, start_year=2025, years_ahead=4):
        """
        Прогноз выпуска инженеров через N лет на основе коэффициента сохранения контингента
        """
        df_retention = self.calculate_retention_by_cohort(2020, 2023)
    
        if df_retention is None or df_retention.empty:
            print("Нет исторических данных для расчета коэффициентов сохранности")
            return None
    
         # Базовые коэффициенты для направлений без истории
        default_rates = {
            'Бакалавриат': 0.65,  
            'Специалитет': 0.87,  
            'Магистратура': 0.71  
        }

        retention_by_code = {}
        for code in df_retention['code'].unique():
            code_df = df_retention[df_retention['code'] == code]
            # Средняя сохранность по годам
            avg_retention = code_df['retention_rate'].mean() / 100
            # Уровень образования
            level = code_df['education_level'].iloc[0]
            # Количество лет данных
            years_count = len(code_df)
        
            retention_by_code[code] = {
                'rate': avg_retention,
                'level': level,
                'years_count': years_count
            }
    
        cursor = self._conn.cursor()
        cursor.execute("SELECT MIN(year), MAX(year) FROM admissions")
        min_year, max_year = cursor.fetchone()
    
        if max_year is None:
            print("Нет данных о приеме")
            return None

        current_year = datetime.now().year
       # print("Коэф. сохранности по направлениям:")
    
        #for code, data in retention_by_code.items():
         #   print(f"  {code:<10} {data['rate']*100:>5.1f}% (на основе {data['years_count']} лет, {data['level']})")
    
        start_year_actual = max_year - 4
        if start_year_actual < min_year:
            start_year_actual = min_year


        query = """
        SELECT 
        sf.code,
        sf.name,
        sf.broad_group,
        el.name as education_level,
        a.year as admission_year,
        a.admitted_total,
        CASE 
            WHEN el.name = 'Бакалавриат' THEN 4
            WHEN el.name = 'Специалитет' THEN 5
            WHEN el.name = 'Магистратура' THEN 2
            ELSE 4
        END as duration
    FROM admissions a
    JOIN study_fields sf ON a.study_field_id = sf.id
    JOIN education_levels el ON a.education_level_id = el.id
    WHERE sf.is_itr = TRUE
      AND a.year BETWEEN %s AND %s
    ORDER BY sf.code, a.year
           """
    
        df_all = pd.read_sql(query, self._conn,params=(start_year_actual, max_year))
        if df_all.empty:
            print("Нет данных для прогноза выпуска")
            return None
    
        max_real_year = df_all['admission_year'].max()

        start_years_by_level = {}
    
        # Для бакалавриата (4 года)
        bachelor_last_year = df_all[df_all['education_level'] == 'Бакалавриат']['admission_year'].max()
        if bachelor_last_year is not None:
            start_years_by_level['Бакалавриат'] = max(min_year, bachelor_last_year - 4)
    
        # Для специалитета (5 лет)
        specialist_last_year = df_all[df_all['education_level'] == 'Специалитет']['admission_year'].max()
        if specialist_last_year is not None:
            start_years_by_level['Специалитет'] = max(min_year, specialist_last_year - 5)
    
        # Для магистратуры (2 года)
        master_last_year = df_all[df_all['education_level'] == 'Магистратура']['admission_year'].max()
        if master_last_year is not None:
            start_years_by_level['Магистратура'] = max(min_year, master_last_year - 2)
    

        df_admissions_list = []
    
        for level, start_year in start_years_by_level.items():
            df_level = df_all[
                (df_all['education_level'] == level) & 
                (df_all['admission_year'] >= start_year)
            ].copy()
            df_admissions_list.append(df_level)
    
        if df_admissions_list:
            df_admissions = pd.concat(df_admissions_list, ignore_index=True)
        else:
            print("Нет данных для прогноза")
            return None

        df_admissions = df_admissions.sort_values(['code', 'admission_year'])

       # df_admissions = pd.read_sql(query, self._conn, params=(start_years_by_level,max_year ))
    

        fill_missing = True

        if fill_missing:
            active_specs = set()
            for level in df_admissions['education_level'].unique():
                    level_data = df_admissions[df_admissions['education_level'] == level]
                    last_year = level_data['admission_year'].max()
        
                    active = level_data[level_data['admission_year'] == last_year]['code'].unique()
                    active_specs.update(active)
                    
            for level in df_admissions['education_level'].unique():
                level_mask = df_admissions['education_level'] == level
            
                # Определяем длительность обучения для определения нужных лет
                duration = df_admissions[level_mask]['duration'].iloc[0] if level_mask.any() else 4
            
                # Получаем уникальные специальности этого уровня
                specs_in_level = df_admissions[level_mask]['code'].unique()


                for code in specs_in_level:
                    if code not in active_specs:
                        continue
                    code_mask = (df_admissions['code'] == code) & (df_admissions['education_level'] == level)
                    code_data = df_admissions[code_mask].copy()
                
                    if code_data.empty:
                        continue
                
                    # Получаем последний год приёма для этой специальности
                    last_admission_year = code_data['admission_year'].max()
                    last_admitted = code_data[code_data['admission_year'] == last_admission_year]['admitted_total'].iloc[0]
                
                    # Определяем, какие годы нужны для прогноза выпуска
                    current_year = datetime.now().year
                    needed_years = []
                
                    for year_offset in range(1, years_ahead + 3):
                        future_year = last_admission_year + year_offset
                        graduation_year = future_year + duration
                    
                        #  актуален ли этот выпуск
                        if graduation_year >= current_year and graduation_year <= max_year + years_ahead + 2:
                            needed_years.append(future_year)
                
                    # заполняем недостающие годы последним известным значением
                    for year in needed_years:
                        if year > last_admission_year:
                            # Проверяем, есть ли уже данные за этот год
                            existing = df_admissions[
                                (df_admissions['code'] == code) & 
                                (df_admissions['education_level'] == level) & 
                                (df_admissions['admission_year'] == year)
                            ]
                        
                            if existing.empty:
                                if year <= max_real_year:
                                    continue

                                new_row = pd.DataFrame([{
                                    'code': code,
                                    'name': code_data['name'].iloc[0],
                                    'broad_group': code_data['broad_group'].iloc[0],
                                    'education_level': level,
                                    'admission_year': year,
                                    'admitted_total': last_admitted,
                                    'duration': duration
                                }])
                                df_admissions = pd.concat([df_admissions, new_row], ignore_index=True)

            df_admissions = df_admissions.sort_values(['code', 'admission_year'])
        


        forecast_data = []
        total_admitted = 0
        total_forecast = 0

        for _, row in df_admissions.iterrows():
            code = row['code']
            name = row['name']
            level = row['education_level']
            admission_year = row['admission_year']
            admitted = row['admitted_total']
            duration = row['duration']
            graduation_year = admission_year + duration

            
            if graduation_year < current_year:
                continue  #  уже прошедшие годы
        
            if graduation_year > max_year + years_ahead:
                continue  #  слишком далекие годы
        
            # Выбор коэф сохранности
            ''' if code in retention_by_code:
                # реальный коэффициент из истории
                retention_rate = retention_by_code[code]['rate']
                source = f"история ({retention_by_code[code]['years_count']} лет)"
            else:'''
                #баз коэф
            retention_rate = default_rates.get(level, 0.75)
            source = f"базовый (для {level})"
              
                
            if retention_rate > 1:
                retention_rate = 0.95
                source = f"скорректированный (был >100%)"

            forecast_graduates = int(admitted * retention_rate)

            total_admitted += admitted
            total_forecast += forecast_graduates

            forecast_data.append({
            'code': code,
            'name': name,
            'education_level': level,
            'admission_year': admission_year,
            'graduation_year': graduation_year,
            'admitted': int(admitted),
            'forecast_graduates': forecast_graduates,
            'retention_rate': round(retention_rate * 100, 1),
            'source': source
        })
    
        df_forecast = pd.DataFrame(forecast_data)    
    
    
        # Группировка по году выпуска
        summary = df_forecast.groupby('graduation_year').agg({
            'forecast_graduates': 'sum',
            'code': 'count'
        }).round(0).reset_index()
        summary.columns = ['Год выпуска', 'Прогноз выпуска (чел.)', 'Кол-во направлений']
    

        '''
        print(f"  Период приема: {start_year_actual}-{max_year} гг.")
        print(f"  Всего направлений в прогнозе: {len(df_forecast)}")
        print(f"  Всего принято: {total_admitted:,} чел.")
        print(f"  Прогноз выпуска: {total_forecast:,} чел.")
        print(summary.to_string(index=False))'''
  
  
        print(summary.to_string(index=False))
    
        return df_forecast
    
    def get_admission_data(self, top_n=8, quiet=False):
        top_query = """
        WITH yearly_data AS (
            SELECT 
                sf.code,
                sf.name,
                SUM(a.admitted_total) as total_admitted,
                COALESCE(SUM(g.graduates_total), 0) as total_graduates
            FROM study_fields sf
            JOIN admissions a ON sf.id = a.study_field_id
            LEFT JOIN graduations g ON sf.id = g.study_field_id 
                AND a.year = g.year
                AND a.education_level_id = g.education_level_id
            WHERE sf.is_itr = TRUE
              AND a.year >= 2020
            GROUP BY sf.code, sf.name
            ORDER BY (SUM(a.admitted_total) + COALESCE(SUM(g.graduates_total), 0)) DESC
            LIMIT %s
        )
        SELECT code, name FROM yearly_data
        """
    
        cursor = self._conn.cursor()
        cursor.execute(top_query, (top_n,))
        top_fields = cursor.fetchall()
        top_codes = [f[0] for f in top_fields]
    
        if not top_codes:
            return None
    
  
        codes_str = "', '".join(top_codes)
  
        query = f"""
        SELECT 
            sf.code,
            sf.name,
            a.year,
            SUM(a.admitted_total) as admitted,
            COALESCE(SUM(g.graduates_total), 0) as graduates
        FROM study_fields sf
        JOIN admissions a ON sf.id = a.study_field_id
        LEFT JOIN graduations g ON sf.id = g.study_field_id 
            AND a.year = g.year
            AND a.education_level_id = g.education_level_id
        WHERE sf.is_itr = TRUE
          AND a.year >= 2020
          AND sf.code IN ('{codes_str}')
        GROUP BY sf.code, sf.name, a.year
        ORDER BY sf.code, a.year
        """

        return pd.read_sql(query, self._conn)

    @staticmethod
    def admis_report(df, top_n=8):
        if df is None or df.empty:
            return "Нет данных для отображения"

        output_lines = []      
        output_lines.append("Статистика по направлениям")
        output_lines.append(f"{'Код':<10} {'Принято':>12} {'Выпущено':>12} {'Общая сохранность':>14}") 
        
        summary = df.groupby(['code', 'name']).agg({
                'admitted': 'sum',
                'graduates': 'sum'
        }).round(0).sort_values('admitted', ascending=False)
        summary.columns = ['Всего принято', 'Всего выпущено']
        summary['Общая сохранность (%)'] = (summary['Всего выпущено'] / summary['Всего принято'] * 100).round(1)
        
        summary_reset = summary.reset_index()
    
        for _, row in summary_reset.head(top_n).iterrows():
            output_lines.append(f"{row['code']:<10} {row['Всего принято']:>10,} {row['Всего выпущено']:>10,} {row['Общая сохранность (%)']:>12.1f}%")
        return "\n".join(output_lines)
    
  
    def calculate_retention_by_cohort(self, start_year=2020, end_year=2025):
        """
        Рассчитывает сохранность по когортам (годам приёма)
        """
        query = """
        SELECT 
        sf.code,
        sf.name,
        sf.is_itr,
        el.name as education_level,
        a.year as admission_year,
        a.admitted_total as admitted,
        COALESCE(g.graduates_total, 0) as graduates,
        CASE 
            WHEN el.name = 'Бакалавриат' THEN 4
            WHEN el.name = 'Специалитет' THEN 5
            WHEN el.name = 'Магистратура' THEN 2
            ELSE 4
        END as duration
    FROM admissions a
    JOIN study_fields sf ON a.study_field_id = sf.id
    JOIN education_levels el ON a.education_level_id = el.id
    LEFT JOIN graduations g ON g.study_field_id = sf.id 
        AND g.year = a.year + CASE 
            WHEN el.name = 'Бакалавриат' THEN 4
            WHEN el.name = 'Специалитет' THEN 5
            WHEN el.name = 'Магистратура' THEN 2
            ELSE 4
        END
        AND g.education_level_id = a.education_level_id
    WHERE sf.is_itr = TRUE
      AND a.year BETWEEN %s AND %s
    ORDER BY sf.code, a.year
        """
    
        df = pd.read_sql(query, self._conn, params=(start_year, end_year))
    
        if df.empty:
            return None


        results = []
    
        for _, row in df.iterrows():
            admitted = row['admitted']
            graduated = row['graduates']
            duration = row['duration']

            if graduated > admitted:
           
                logger.warning(f"Несоответствие: {row['code']} ({row['education_level']}), "
                          f"прием={admitted}, выпуск={graduated}, год приема={row['admission_year']}")
            
                graduated = admitted
        
            if admitted > 0:
                retention = round(graduated / admitted * 100, 1)
            else:
                retention = 0
        
            results.append({
                'code': row['code'],
                'name': row['name'],
                'education_level': row['education_level'],
                'admission_year': row['admission_year'],
                'admitted': int(admitted),
                'graduated': int(graduated),
                'retention_rate': retention,
                'is_itr': row['is_itr']
            })
    
        return pd.DataFrame(results)


    def print_retention_comparison(self, start_year=2020, end_year=2025):
        """
        Выводит сравнение сохранности по годам приёма для ИТР-направлений
        """
        df = self.calculate_retention_by_cohort(start_year, end_year)
    
        if df is None or df.empty:
            print("Нет данных для расчёта")
            return

        df_itr = df[df['is_itr'] == True]
    
     
        print("Сохранность по  когортам")
       
        print(f"{'Код':<10} {'Направление':<35} ", end="")
    
        # Заголовки по годам
        years = sorted(df_itr['admission_year'].unique())
        for y in years:
            print(f"{y:>8}", end="")
        print(f"{'Средняя':>10}")
       
    
        # Данные по каждому направлению
        for code in df_itr['code'].unique():
            code_df = df_itr[df_itr['code'] == code]
            name = code_df['name'].iloc[0][:33]
        
            print(f"{code:<10} {name:<35} ", end="")
        
            retention_by_year = []
            for y in years:
                val = code_df[code_df['admission_year'] == y]['retention_rate'].values
                rate = val[0] if len(val) > 0 else 0
                print(f"{rate:>7.1f}%", end="")
                if rate > 0:
                    retention_by_year.append(rate)
        
            avg = round(sum(retention_by_year) / len(retention_by_year), 1) if retention_by_year else 0
            print(f"{avg:>9.1f}%")

       
        print(f"{'Средняя:':<46} ", end="")
    
        for y in years:
            year_avg = df_itr[df_itr['admission_year'] == y]['retention_rate'].mean()
            print(f"{year_avg:>7.1f}%", end="")
    
        total_avg = df_itr['retention_rate'].mean()
        print(f"{total_avg:>9.1f}%")
    
        return df


    def get_retention_summary(self, start_year=2020, end_year=2023):
        """
        Возвращает сводку сохранности (для использования в GUI)
        """
        df = self.calculate_retention_by_cohort(start_year, end_year)
    
        if df is None or df.empty:
            return "Нет данных для расчёта сохранности"
    
        df_itr = df[df['is_itr'] == True]
    
        output_lines = []
        
        output_lines.append("Сохранность по годам приема")

        education_levels = sorted(df_itr['education_level'].unique())
    
        for level in education_levels:
            df_level = df_itr[df_itr['education_level'] == level]
            if df_level.empty:
                continue
        
            output_lines.append(f"\n{level}:")

            years = sorted(df_level['admission_year'].unique())

            # Заголовок таблицы
            header = f"{'Код':<10} {'Направление':<35}"
            for y in years:
                header += f" {y:>7}"
            header += f" {'Ср.':>8}"
            output_lines.append(header)
            

            # Данные по направлениям
            for code in sorted(df_level['code'].unique()):
                code_df = df_level[df_level['code'] == code]
                if code_df.empty:
                    continue
                
                name = code_df['name'].iloc[0][:33]
        
                line = f"{code:<10} {name:<35}"
                retention_vals = []
        
                for y in years:
                    val = code_df[code_df['admission_year'] == y]['retention_rate'].values
                    rate = val[0] if len(val) > 0 else 0
                    display_rate = min(rate, 100) if rate > 0 else 0
                    line += f" {display_rate:>6.1f}%"
                    if 0 < rate <= 100:  
                        retention_vals.append(rate)
        
                avg = round(sum(retention_vals) / len(retention_vals), 1) if retention_vals else 0
                line += f" {avg:>7.1f}%"
                output_lines.append(line)

            avg_line = f"{'Средняя по ' + level + ':':<46}"
            for y in years:
                year_data = df_level[df_level['admission_year'] == y]
                if not year_data.empty:
                    year_avg = year_data['retention_rate'].mean()
                    year_avg = min(year_avg, 100) if not pd.isna(year_avg) else 0
                else:
                    year_avg = 0
                avg_line += f" {year_avg:>6.1f}%"

            total_avg = df_level['retention_rate'].mean()
            total_avg = min(total_avg, 100) if not pd.isna(total_avg) else 0
            avg_line += f" {total_avg:>7.1f}%"
            output_lines.append(avg_line)
    
        #  общая статистика
     
        output_lines.append("\nОбщая статистика:")
    
        for level in education_levels:
            df_level = df_itr[df_itr['education_level'] == level]
            if not df_level.empty:
                total_admitted = df_level['admitted'].sum()
                total_graduated = df_level['graduated'].sum()
                overall_retention = round(total_graduated / total_admitted * 100, 1) if total_admitted > 0 else 0
                output_lines.append(f"  {level}: {len(df_level['code'].unique())} направлений, "
                                   f"всего принято: {total_admitted:,}, "
                                   f"выпущено: {total_graduated:,}, "
                                   f"общая сохранность: {overall_retention}%")
        

        return "\n".join(output_lines)


        