import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
import numpy as np

from analyse_graduation import  EducationFlowAnalyser

      

def plot_deficit_by_field(analyser, ax = None, show_plot=False, target_year=2025):
    """
    Построение графика сравнения 
    """

    conn = analyser._conn
    
    query = """
    SELECT 
        -- Всего вакансий (сумма по всем записям)
        COALESCE(SUM(active_vacancies), 0) as total_vacancies,
        -- Всего безработных на учёте
        COALESCE(SUM(unemployed_count), 0) as total_unemployed
    FROM labor_market_balance
    """
    
    df_balance = pd.read_sql(query, conn)
    
   
    grad_query = """
    SELECT 
        COALESCE(SUM(graduates_total), 0) as total_graduates
    FROM graduations
    WHERE year = %s
    """
    
    df_grad = pd.read_sql(grad_query, conn, params=(target_year,))
    
    vacancies = df_balance['total_vacancies'].iloc[0]
    unemployed = df_balance['total_unemployed'].iloc[0]
    graduates = df_grad['total_graduates'].iloc[0]
 
    
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
        own_fig = True
    else:
        own_fig = False
    
    categories = ['Вакансии', 'Выпускники', 'Безработные']
    values = [vacancies, graduates, unemployed]
    colors = ['#FF6B6B', '#45B7D1', '#FFA500']
    
    bars = ax.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5, alpha=0.8)
    
    
    max_val = max(values) if max(values) > 0 else 1
    ax.set_ylim(0, max_val * 1.15)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_val * 0.02,
                f'{int(val):,}', ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Количество человек', fontsize=12, fontweight='bold')
    ax.set_title('Сравнение: Вакансии, Выпускники, Безработные на учёте\n', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    #plt.savefig('deficit_by_field.png', dpi=150, bbox_inches='tight')

    if own_fig:
        if show_plot:
            plt.show()
        else:
            plt.close(ax.figure)
    
    
    
    # Вывод статистики
   
    print(f"Всего активных вакансий: {vacancies:,.0f}")
    print(f"Всего выпускников (за последний учебный год): {graduates:,.0f}")
    print(f"Всего безработных на учёте: {unemployed:,.0f}")
    
    if vacancies > 0 and graduates > 0:
        print(f"\nНа одну вакансию могут претендовать(оптимистичный вариант): {(unemployed + graduates) / vacancies:.1f} человек")
        print(f"На одну вакансию могут претендовать(реалистичный вариант): {((unemployed * 0.32) + (graduates * 0.2)) / vacancies:.1f} человек")
    
    
    return pd.DataFrame([{
        'total_vacancies': vacancies,
        'total_graduates': graduates,
        'total_unemployed': unemployed
    }])


def plot_forecast_graduates_graf(ax, analyser, start_year=2025, years_ahead=5):
   
    
    df_forecast =analyser.forecast_graduates_by_year(start_year, years_ahead)
    
    if df_forecast is None or df_forecast.empty:
            ax.text(0.5, 0.5, 'Нет данных для прогноза', transform=ax.transAxes, ha='center')
            return 
    
        # Группируем по годам
    summary = df_forecast.groupby('graduation_year')['forecast_graduates'].sum().reset_index()
    
  #  fig, ax = plt.subplots(figsize=(10, 6))
    
    years = summary['graduation_year'].astype(int).values
    values = summary['forecast_graduates'].values
    colors = plt.cm.Blues(np.linspace(0.5, 0.9, len(years)))
    
    
    max_val = max(values) if len(values) > 0 else 1
    ax.set_ylim(0, max_val * 1.15)

    ax.plot(years, values, 'o-', color='steelblue', linewidth=2, markersize=8, label='Прогноз')
    
    # Добавляем значения на точки
    for x, y in zip(years, values):
        if y > max_val * 0.85:
            offset = -15  # Текст снизу
            va = 'top'
        else:
            offset = 10   # Текст сверху
            va = 'bottom'
        ax.annotate(f'{int(y):,}', (x, y), textcoords="offset points", 
                   xytext=(0, offset), ha='center', fontsize=9)


    ax.set_xticks(years)
    ax.set_xticklabels([str(int(x)) for x in years])

    ax.set_xlabel('Год')
    ax.set_ylabel('Кол-во выпускников')
    ax.set_title('Прогноз выпуска инженерных кадров')
    ax.grid(True, alpha=0.3, axis='y')
    
    ax.legend(loc='center left', bbox_to_anchor=(0.995, 0.5), fontsize=10, frameon=True, fancybox=True, shadow=True)
    
    
    
def plot_forecast_graduates_bar(ax, analyser, start_year=2025, years_ahead=4):
    
    df_forecast = analyser.forecast_graduates_by_year(start_year, years_ahead)
    
    if df_forecast is None or df_forecast.empty:
        ax.text(0.5, 0.5, 'Нет данных для прогноза', transform=ax.transAxes, ha='center')
        return 
    
    # Группируем по годам
    summary = df_forecast.groupby('graduation_year')['forecast_graduates'].sum().reset_index()
    
    years = summary['graduation_year'].astype(int).values
    values = summary['forecast_graduates'].values
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(years)))
    
    # Столбчатая диаграмма
    bars = ax.bar(years, values, color=colors, edgecolor='black', linewidth=1.5, alpha=0.8)
    
   
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                f'{int(val):,}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_xlabel('Год выпуска', fontsize=11)
    ax.set_ylabel('Кол-во выпускников', fontsize=11)
    ax.set_title('Прогноз выпуска инженерных кадров', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Устанавливаем все годы на оси X
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years])

def plot_full_admission_analysis(ax1, ax2, ax3, analyser, top_n=8):
    """
    Рисует полный анализ приёма и выпуска на трёх переданных осях
    """
    df = analyser.get_admission_data( top_n=top_n)
    
    if df is None or df.empty:
        for ax in [ax1, ax2, ax3]:
            ax.text(0.5, 0.5, 'Нет данных', transform=ax.transAxes, ha='center')
        return df
    
    fields = df[['code', 'name']].drop_duplicates()
    colors = plt.cm.Set3(np.linspace(0, 1, len(fields)))
    
    # Приём
    for idx, (_, field) in enumerate(fields.iterrows()):
        field_data = df[df['code'] == field['code']]
        ax1.plot(field_data['year'], field_data['admitted'], 
                'o-', color=colors[idx], linewidth=2, markersize=8,
                label=field['code'])
    ax1.set_ylabel('Поступившие')
    ax1.set_title('Динамика приёма')
    ax1.legend(loc='center right', bbox_to_anchor=(1.06, 0.5))
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks([2023, 2024, 2025])
    
    # Выпуск
    for idx, (_, field) in enumerate(fields.iterrows()):
        field_data = df[df['code'] == field['code']]
        ax2.plot(field_data['year'], field_data['graduates'], 
                's-', color=colors[idx], linewidth=2, markersize=8,
                label=field['code'])
    ax2.set_ylabel('Кол-во выпускников')
    ax2.set_title('Динамика выпуска')
    ax2.legend(loc='center right', bbox_to_anchor=(1.06, 0.5))
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks([2023, 2024, 2025])
    
    # Прогноз
    plot_forecast_graduates_graf(ax3, analyser, start_year=2027, years_ahead=3)
    
    return df


#график приема
def plot_admission_chart(ax, df):
    """График приёма на переданной оси"""
    fields = df[['code', 'name']].drop_duplicates()
    colors = plt.cm.Set3(np.linspace(0, 1, len(fields)))
    for idx, (_, field) in enumerate(fields.iterrows()):
        field_data = df[df['code'] == field['code']]
        ax.plot(field_data['year'], field_data['admitted'], 
               'o-', color=colors[idx], linewidth=2, markersize=8,
               label=field['code'])
    ax.set_ylabel('Кол-во поступивших')
    ax.set_title('Динамика приёма')
    #ax.legend(loc='best')
    ax.legend(loc='center left', bbox_to_anchor=(0.995, 0.5), fontsize=10, frameon=True, fancybox=True, shadow=True)
    ax.grid(True, alpha=0.3)
    ax.set_xticks([2020, 2021, 2022, 2023, 2024, 2025])

def plot_graduation_chart(ax, df):
    """Рисует график выпуска на переданной оси"""
    fields = df[['code', 'name']].drop_duplicates()
    colors = plt.cm.Set3(np.linspace(0, 1, len(fields)))
    for idx, (_, field) in enumerate(fields.iterrows()):
        field_data = df[df['code'] == field['code']]
        ax.plot(field_data['year'], field_data['graduates'], 
               's-', color=colors[idx], linewidth=2, markersize=8,
               label=field['code'])
    ax.set_ylabel('Кол-во выпускников')
    ax.set_title('Динамика выпуска')
    ax.legend(loc='center left', bbox_to_anchor=(0.995, 0.5), fontsize=10, frameon=True, fancybox=True, shadow=True)
    
    ax.grid(True, alpha=0.3)
    ax.set_xticks([2020, 2021, 2022, 2023, 2024, 2025])



