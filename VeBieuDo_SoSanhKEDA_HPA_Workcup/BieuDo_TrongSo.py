import pandas as pd
import matplotlib.pyplot as plt
import re
import os

# --- CẤU HÌNH ---
THRESHOLDS = {
    'frontend': {'CPU': 70.0, 'RPS': 37.0, 'Memory': 400.0, 'Error': 0.01},
    'productcatalogservice': {'CPU': 70.0, 'RPS': 110.0, 'Memory': 300.0, 'Error': 0.01}
}
# Thay đổi tên file log cho đúng với file của em
FILE_LOG = 'Log_Keda.txt' 

def analyze_keda_log(filename):
    if not os.path.exists(filename):
        print(f"❌ Không tìm thấy file: {filename}")
        return pd.DataFrame()
    events = []
    try:
        with open(filename, 'r', encoding='utf-8') as f: lines = f.readlines()
    except:
        with open(filename, 'r', encoding='utf-16') as f: lines = f.readlines()

    last_pods = {'frontend': 1, 'productcatalogservice': 1}
    pattern = re.compile(r'\| (.*?) \| CPU: ([\d.]+) % \| RAM: ([\d.]+) MB \| RPS: ([\d.]+) \| ERROR: ([\d.]+) \| PODS: (\d+)')

    for line in lines:
        match = pattern.search(line)
        if match:
            svc = match.group(1).strip()
            cpu, ram, rps, err, pods = map(float, [match.group(2), match.group(3), match.group(4), match.group(5), match.group(6)])
            pods = int(pods)
            
            if pods > last_pods[svc]:
                diff = pods - last_pods[svc]
                # Ưu tiên xác định Trigger gây ra việc scale
                if rps >= THRESHOLDS[svc]['RPS']: trigger_hit = 'RPS'
                elif cpu >= THRESHOLDS[svc]['CPU']: trigger_hit = 'CPU'
                elif ram >= THRESHOLDS[svc]['Memory']: trigger_hit = 'Memory'
                elif err >= THRESHOLDS[svc]['Error']: trigger_hit = 'Error'
                else: trigger_hit = 'Khác'
                
                events.append({'Dịch vụ': svc, 'Trigger': trigger_hit, 'Pods_Tang': diff})
            last_pods[svc] = pods
    return pd.DataFrame(events)

# Thực thi phân tích
df_events = analyze_keda_log(FILE_LOG)

if not df_events.empty:
    summary = df_events.groupby(['Dịch vụ', 'Trigger'])['Pods_Tang'].sum().unstack(fill_value=0)
    for col in ['CPU', 'Memory', 'RPS', 'Error']:
        if col not in summary.columns: summary[col] = 0

    # Vẽ biểu đồ
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), sharey=True)
    fig.suptitle('ĐÁNH GIÁ TRỌNG SỐ ĐÓNG GÓP THỰC TẾ CỦA CÁC EVENT TRIGGER (KEDA)', 
                 fontsize=22, fontweight='bold', y=0.98)

    mapping = {'frontend': (ax1, 'Dịch vụ FRONTEND'), 
               'productcatalogservice': (ax2, 'Dịch vụ PRODUCT')}

    for svc_id, (ax, title) in mapping.items():
        if svc_id in summary.index:
            data = summary.loc[svc_id][['CPU', 'Memory', 'RPS', 'Error']]
            colors = ['#ff7675', '#fdcb6e', '#74b9ff', '#a29bfe']
            bars = ax.bar(data.index, data.values, color=colors, edgecolor='black', alpha=0.8, width=0.6)
            
            ax.set_title(title, fontsize=18, fontweight='bold', pad=25)
            ax.set_ylabel('Tổng số Pod được tạo thêm', fontsize=14, fontweight='bold')
            ax.grid(axis='y', linestyle=':', alpha=0.6)
            
            # Khống chế trục Y để không bị che chữ
            ax.set_ylim(0, 6) 
            
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., h + 0.2, f'+{int(h)} Pod', 
                            ha='center', va='bottom', fontweight='bold', fontsize=15)

    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    
    # --- XUẤT FILE ---
    plt.savefig('TrongSo_KEDA_Final.png', dpi=300)
    plt.savefig('TrongSo_KEDA_Final.svg', format='svg', bbox_inches='tight')
    
    print("✅ Đã xuất xong file PNG và SVG siêu nét cho Nhu!")
    plt.show()
else:
    print("⚠️ Log không có dữ liệu scale-up để vẽ.")