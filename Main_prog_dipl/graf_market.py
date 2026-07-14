import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
import numpy as np

def plot_market_chart(conn, ax=None, show_plot=False):
    """Возвращает DataFrame с данными по рынку"""
    query = """
    SELECT 
        p.name AS position_name,
        SUM(lb.active_vacancies) AS vacancies,
        SUM(lb.unemployed_count) AS unemployed
    FROM labor_market_balance lb
    JOIN positions p ON lb.position_id = p.id
    GROUP BY p.name
    ORDER BY vacancies DESC
    LIMIT 20
    """
    df = pd.read_sql(query, conn)

    df_result = df.copy()

    df.columns = ['Должность', 'Вакансии', 'Безработные']
   # df['position_name'] = df['position_name'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)
    df['Должность'] = df['Должность'].apply(lambda x: x[:35] + '...' if len(x) > 35 else x)
    
    print("Данные по должностям:")
    print(df.to_string(index=False))
    #print(f"\nВсего вакансий: {df['Вакансии'].sum()}")
    #print(f"Всего безработных: {df['Безработные'].sum()}")
    
    if ax is not None:
        x = np.arange(len(df))
        width = 0.35
        ax.bar(x - width/2, df['Вакансии'], width, label='Вакансии', color='#FF6B6B')
        ax.bar(x + width/2, df['Безработные'], width, label='Безработные', color='#4ECDC4')
        ax.set_xlabel('Должность', fontsize=10)
        ax.set_ylabel('Количество', fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(df['Должность'], rotation=45, ha='right', fontsize=8)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
    elif show_plot:
        # Если ax не передан, но show_plot=True, создаем отдельное окно
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(14, 10))
        x = np.arange(len(df))
        width = 0.35
        ax.bar(x - width/2, df['Вакансии'], width, label='Вакансии', color='#FF6B6B')
        ax.bar(x + width/2, df['Безработные'], width, label='Безработные', color='#4ECDC4')
        ax.set_xlabel('Должность', fontsize=12)
        ax.set_ylabel('Количество', fontsize=12)
        ax.set_title('Количество вакансий и безработных по должностям', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(df['Должность'], rotation=45, ha='right', fontsize=8)
        ax.legend()
        plt.tight_layout()
        plt.show()
    
    return df_result


def get_average_salary(conn, top_n=20):
    """
    Рассчит средн, мин и макс зп по профессиям
  
    """
    query = """
    SELECT 
        p.name AS position_name,
        ROUND(AVG(lb.salary_min)) as avg_salary_min,
        ROUND(AVG(lb.salary_max)) as avg_salary_max,
        ROUND((AVG(lb.salary_min) + AVG(lb.salary_max)) / 2) as avg_salary_mid,
        COUNT(lb.position_id) as vacancies_count,
        MIN(lb.salary_min) as min_salary,
        MAX(lb.salary_max) as max_salary
    FROM labor_market_balance lb
    JOIN positions p ON lb.position_id = p.id
      AND lb.salary_min > 0
      AND lb.salary_max > 0
    GROUP BY p.name
    ORDER BY avg_salary_mid DESC
    LIMIT %s
    """
    
    df = pd.read_sql(query, conn, params=(top_n,))
    
    if df.empty:
        print("Нет данных о зарплатах")
        return df
    
 
    print("Средние зарплаты по профессиям ")

    print(f"{'Профессия':<35} {'Мин. (ср.)':>12} {'Макс. (ср.)':>12} {'Средняя':>12}")

    
    for _, row in df.iterrows():
        name = row['position_name'][:33] if len(row['position_name']) > 33 else row['position_name']
        print(f"{name:<35} {row['avg_salary_min']:>12,} {row['avg_salary_max']:>12,} "
              f"{row['avg_salary_mid']:>12,}")
    
    return df


def plot_salary_chart(df, show_plot=False, ax=None):
    """
    Построение графика средних зарплат по профессиям
    """
   
    
    if df.empty:
        print("Нет данных для построения графика")
        return None
      
    
    # Сортируем по убыванию
    df_sorted = df.sort_values('avg_salary_mid', ascending=True)
    
    y_pos = np.arange(len(df_sorted))
    salary_mid = df_sorted['avg_salary_mid'].values
    names = df_sorted['position_name'].apply(lambda x: x[:25] + '...' if len(x) > 25 else x)
    
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 10))
        own_fig = True
    else:
        own_fig = False


    # Горизонтальные столбцы
    bars = ax.barh(y_pos, salary_mid, color='steelblue', edgecolor='black', alpha=0.8)
    
  
    for bar, val in zip(bars, salary_mid):
        ax.text(bar.get_width() + 500, bar.get_y() + bar.get_height()/2,
               f'{int(val):,}', ha='left', va='center', fontsize=9)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel('Средняя зарплата (руб.)', fontsize=12)
    ax.set_title('Средние зарплаты по ИТР-профессиям', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    
    
    #plt.savefig('salary_chart.png', dpi=150, bbox_inches='tight')
    #print("\nГрафик сохранён как 'salary_chart.png'")
    
    if own_fig:
        plt.tight_layout()
        if show_plot:
            plt.show()
        else:
            plt.close(fig)
    
   
    
    return df