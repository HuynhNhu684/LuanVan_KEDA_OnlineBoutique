import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D # Import thêm cái này để tự tạo Legend xịn
import re
import os

# --- CẤU HÌNH ---
THRESHOLDS = {
    'frontend': {'CPU': 70.0, 'RPS': 37.0, 'Memory': 400.0, 'Error': 0.01},
    'productcatalogservice': {'CPU': 70.0, 'RPS': 83.0, 'Memory': 300.0, 'Error': 0.01} 
}
# Chú ý: Đảm bảo tên file này giống 100% tên file trong máy em nha
FILE_LOG = 'Log_Keda_TQ.txt' 

# ==========================================
# 1. ĐỌC DỮ LIỆU & TÌM KIẾM ĐIỂM SCALE-UP
# ==========================================
def get_service_data(filename):
    if not os.path.exists(filename):
        print(f"❌ Không tìm thấy file: {filename}")
        return pd.DataFrame(), pd.DataFrame()
        
    data = []
    try:
        try:
            with open(filename, 'r', encoding='utf-8') as f: lines = f.readlines()
        except:
            with open(filename, 'r', encoding='utf-16') as f: lines = f.readlines()
            
        pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*(.*?)\s*\|\s*CPU:\s*([\d.]+)\s*%\s*\|\s*RAM:\s*([\d.]+)\s*MB\s*\|\s*RPS:\s*([\d.]+)\s*\|\s*ERROR:\s*([\d.]+)\s*\|\s*PODS:\s*(\d+)')
        
        for line in lines:
            match = pattern.search(line)
            if match:
                data.append({
                    'Datetime': pd.to_datetime(match.group(1)),
                    'Service': match.group(2).strip(),
                    'CPU': float(match.group(3)),
                    'Memory': float(match.group(4)), 
                    'RPS': float(match.group(5)),
                    'Error': float(match.group(6)),
                    'Pods': int(match.group(7))
                })
    except Exception as e:
        print(f"Lỗi đọc file: {e}")
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(data)
    if df.empty: 
        return pd.DataFrame(), pd.DataFrame()
    
    df['Time_sec'] = (df['Datetime'] - df['Datetime'].min()).dt.total_seconds()
    return df[df['Service'] == 'frontend'].copy(), df[df['Service'] == 'productcatalogservice'].copy()

def extract_scale_events(df, svc_name):
    events = []
    last_pods = 1
    
    for idx, row in df.iterrows():
        current_pods = int(row['Pods'])
        if current_pods > last_pods:
            diff = current_pods - last_pods
            if row['RPS'] >= THRESHOLDS[svc_name]['RPS']: trigger = 'RPS'
            elif row['CPU'] >= THRESHOLDS[svc_name]['CPU']: trigger = 'CPU'
            elif row['Error'] >= THRESHOLDS[svc_name]['Error']: trigger = 'Error'
            else: trigger = 'CPU/Khác' 
            
            events.append({
                'Time_sec': row['Time_sec'],
                'Pods': current_pods,
                'Diff': diff,
                'Trigger': trigger
            })
        last_pods = current_pods
    return pd.DataFrame(events)

# ==========================================
# 2. VẼ BIỂU ĐỒ TIMELINE GẮN NHÃN TỐI GIẢN
# ==========================================
print("🚀 Đang vẽ biểu đồ Timeline tối giản...")
df_fe, df_pc = get_service_data(FILE_LOG)

if df_fe.empty and df_pc.empty:
    print("❌ Dừng vẽ vì không có dữ liệu nào cả.")
else:
    # BÓP NHỎ BIỂU ĐỒ XUỐNG 14x8
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle('TIMELINE ĐÓNG GÓP CỦA CÁC EVENT TRIGGER (KEDA SCALE-UP)', 
                 fontsize=20, fontweight='bold', y=0.98)

    services = [
        ('frontend', df_fe, ax1, 'DỊCH VỤ FRONTEND', '#2980B9'),
        ('productcatalogservice', df_pc, ax2, 'DỊCH VỤ PRODUCT CATALOG', '#8E44AD')
    ]

    TRIGGER_COLORS = {'RPS': '#E67E22', 'CPU': '#C0392B', 'Error': '#E74C3C', 'CPU/Khác': '#7F8C8D'}

    for svc_name, df_svc, ax, title, line_color in services:
        if not df_svc.empty:
            ax.plot(df_svc['Time_sec'], df_svc['Pods'], color=line_color, linewidth=2.5, 
                    drawstyle='steps-post')
            ax.fill_between(df_svc['Time_sec'], df_svc['Pods'], step='post', color=line_color, alpha=0.1)
            
            df_events = extract_scale_events(df_svc, svc_name)
            
            if not df_events.empty:
                for _, ev in df_events.iterrows():
                    t_color = TRIGGER_COLORS.get(ev['Trigger'], 'black')
                    
                    # Giữ lại dấu chấm tròn rõ nét
                    ax.plot(ev['Time_sec'], ev['Pods'], marker='o', markersize=9, 
                            color=t_color, markeredgecolor='white', markeredgewidth=1.5, zorder=5)
                    
                    # XÓA KHUNG BBOX, CHỈ ĐỂ CHỮ TRẦN LƠ LỬNG
                    text_label = f"+{int(ev['Diff'])}"
                    ax.annotate(text_label, 
                                xy=(ev['Time_sec'], ev['Pods']), 
                                xytext=(0, 8), # Nâng nhẹ lên 8 points so với dấu chấm
                                textcoords='offset points',
                                fontsize=12, fontweight='bold', color=t_color,
                                ha='center', va='bottom', zorder=10)

            ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
            ax.set_ylabel('Số lượng Pods', fontsize=11, fontweight='bold')
            ax.set_ylim(0, df_svc['Pods'].max() + 1.5) 
            ax.grid(True, linestyle=':', alpha=0.6)
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

    # TẠO CHÚ GIẢI (LEGEND) CHUNG CHO CẢ BIỂU ĐỒ ĐỂ GIẢI THÍCH MÀU SẮC
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Kích hoạt bởi: RPS', markerfacecolor='#E67E22', markersize=10),
        Line2D([0], [0], color='#2980B9', lw=2.5, label='Biểu đồ Frontend'),
        Line2D([0], [0], color='#8E44AD', lw=2.5, label='Biểu đồ Product')
    ]
    # Đặt Legend ở góc trên cùng bên phải
    fig.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.95, 0.94),
               fontsize=11, framealpha=0.9, ncol=2)

    ax2.set_xlabel('Thời gian thực thi (Giây)', fontsize=12, fontweight='bold')
    ax2.set_xlim(0, max(df_fe['Time_sec'].max() if not df_fe.empty else 0, 
                        df_pc['Time_sec'].max() if not df_pc.empty else 0) * 1.05)

    plt.tight_layout(rect=[0, 0.03, 1, 0.90]) # Chừa chỗ trống ở trên cho tiêu đề và Legend

    # --- XUẤT FILE ---
    plt.savefig('Timeline_Trigger_KEDA.png', dpi=300, bbox_inches='tight')
    plt.savefig('Timeline_Trigger_KEDA.svg', format='svg', bbox_inches='tight')

    print("✅ Đã thay áo mới! Biểu đồ siêu gọn gàng, hết chồng chữ rồi nha kỹ sư!")
    plt.show()