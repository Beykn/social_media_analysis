import pandas as pd 
from datetime import timedelta
from config import TARGET_USERNAME, follower_history_path
import os 


def generate_weekly_report():
    
    filename = follower_history_path()
    if not os.path.exists(filename):
        return "File does not exists"
    df = pd.read_csv(filename)
    df['date'] = pd.to_datetime(df['date'])
    
    if len(df) < 2:
        print("Not enough data to generate a report.")
        return
    
    last_date = df['date'].max()
    one_week_ago = last_date - timedelta(days=7)
    weekly_data = df[df['date'] >= one_week_ago]
    
    start_value = weekly_data['follower_count'].iloc[0]
    end_value = weekly_data['follower_count'].iloc[-1]
    diff = end_value - start_value
    
    report = f"Weekly Report for {TARGET_USERNAME}:\n"
    report += f"Start Date: {weekly_data['date'].iloc[0].strftime('%Y-%m-%d')}\n"
    report += f"End Date: {weekly_data['date'].iloc[-1].strftime('%Y-%m-%d')}\n"
    report += f"Start Follower Count: {start_value}\n"
    report += f"End Follower Count: {end_value}\n"
    report += f"Difference: {diff}\n"
    report += f"Percentage Change: {diff / start_value * 100:.2f}%\n"
    
    return report