import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import re

# ==========================================
# 1. CÁC HÀM XỬ LÝ DỮ LIỆU
# ==========================================

def load_and_clean_locust(filename):
    df = pd.read_csv(filename)
    df.columns = df.columns.str.strip()
    if 'Name' in df.columns: df = df[df['Name'] == 'Aggregated'].copy()
    df['Time_sec'] = df['Timestamp'] - df['Timestamp'].min()
    
    if 'Total Request Count' in df.columns and 'Total Average Response Time' in df.columns:
        df['Total_Time_Sum'] = df['Total Request Count'] * df['Total Average Response Time']
        req_diff = df['Total Request Count'].diff()
        time_diff = df['Total_Time_Sum'].diff()
        df['Inst_Latency'] = time_diff / req_diff
        df['Inst_Latency'] = df['Inst_Latency'].replace([np.inf, -np.inf], np.nan).ffill().fillna(0)
        df['Inst_Latency'] = df['Inst_Latency'].rolling(window=3, min_periods=1).mean()
    else:
        df['Inst_Latency'] = df['50%']
    return df

def load_hpa_log(filename):
    """
    Hàm đọc trực tiếp file log Text của Kubernetes (HPA / Tĩnh giả lập).
    Sử dụng Regex để bóc tách chính xác CPU và Pods. Tự nhận diện Encoding.
    """
    data = []
    try:
        # Tự động bắt mạch xem file là UTF-16 (PowerShell) hay UTF-8
        try:
            with open(filename, 'r', encoding='utf-16') as f:
                lines = f.readlines()
        except UnicodeError:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
        for line in lines:
            line = line.strip()
            # Bỏ qua dòng tiêu đề hoặc dòng trống
            if not line or 'NAME' in line or 'REFERENCE' in line:
                continue
            
            parts = line.split()
            if len(parts) < 8: 
                continue
            
            # 1. Ghép ngày giờ lại
            date_str = f"{parts[0]} {parts[1]}"
            
            # 2. Phân loại Service
            if "frontend" in line:
                service = "frontend"
            elif "productcatalogservice" in line:
                service = "productcatalogservice"
            else:
                continue
                
            # 3. Lấy thông số CPU bằng Regex (tìm cụm cpu: xxx%/)
            cpu_match = re.search(r'cpu:\s*(<unknown>|\d+)%/', line)
            if cpu_match:
                cpu_val_str = cpu_match.group(1)
                if 'unknown' in cpu_val_str.lower():
                    continue # Bỏ qua khoảnh khắc K8s chưa kịp đo
                cpu_val = int(cpu_val_str)
            else:
                continue
                
            # 4. Lấy số lượng Pod hiện hữu (luôn là cột áp chót trước cột Thời gian AGE)
            try:
                pod_val = int(parts[-2])
            except ValueError:
                continue
                
            data.append({'Datetime': date_str, 'Service': service, 'CPU': cpu_val, 'Pods': pod_val})
            
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy file {filename}")
        return pd.DataFrame(), pd.DataFrame()
        
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
    df = df.dropna(subset=['Datetime'])
    
    # Tính giây thực thi (Time_sec) bắt đầu từ 0
    start_time = df['Datetime'].min()
    df['Time_sec'] = (df['Datetime'] - start_time).dt.total_seconds()
    
    # Tách dữ liệu của 2 Microservices ra độc lập và sắp xếp theo thời gian
    df_fe = df[df['Service'] == 'frontend'].copy().sort_values('Time_sec')
    df_pc = df[df['Service'] == 'productcatalogservice'].copy().sort_values('Time_sec')
    
    return df_fe, df_pc

# ==========================================
# 2. NẠP DỮ LIỆU TỪ LOCUST VÀ LOG TEXT KUBERNETES
# ==========================================
print("Đang nạp dữ liệu Tối thượng (Locust + Log API)...")

# Dữ liệu Locust (Client)
df_locust_no = load_and_clean_locust('No_KEDA_CPU_stats_history.csv')
df_locust_with = load_and_clean_locust('With_KEDA_CPU_stats_history.csv')

# Dữ liệu Hạ tầng trực tiếp từ Log (Server)
fe_no, pc_no = load_hpa_log('Log_Tinh_Standard.txt')
fe_with, pc_with = load_hpa_log('Log_KEDA_Dong.txt')

col_latency = 'Inst_Latency'
col_users = 'User Count'

# Đồng bộ mốc thời gian lớn nhất theo Locust
MAX_TIME = min(df_locust_no['Time_sec'].max(), df_locust_with['Time_sec'].max())
P1_START, P1_END = 0, 180           
P2_START, P2_END = 180, 600         
P3_START, P3_END = 600, 900         
P4_START, P4_END = 900, MAX_TIME    

COLOR_NO, COLOR_WITH = '#e74c3c', '#1f77b4'
COLOR_POD_KEDA, COLOR_POD_NO = '#2ca02c', '#ff7f0e'
COLOR_THRESH = 'darkgrey'

# HÀM TÔ MÀU NỀN & IN NHÃN
def add_phase_bg(ax, show_labels=False):
    ax.axvspan(P1_START, P1_END, color='#e0f7fa', alpha=0.5) 
    ax.axvspan(P2_START, P2_END, color='#fff9c4', alpha=0.5) 
    ax.axvspan(P3_START, P3_END, color='#c8e6c9', alpha=0.5) 
    ax.axvspan(P4_START, P4_END, color='#e1bee7', alpha=0.4) 

    if show_labels:
        bbox_props = dict(facecolor='white', alpha=0.8, edgecolor='none', boxstyle='round,pad=0.3')
        y_pos = 0.5 
        ax.text((P1_START + P1_END)/2, y_pos, 'Khởi động\n(30 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#00838f', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P2_START + P2_END)/2, y_pos, 'Đỉnh tải\n(200 Users)', transform=ax.get_xaxis_transform(), fontsize=11, color='#f57f17', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P3_START + P3_END)/2, y_pos, 'Hạ nhiệt\n(10 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#2e7d32', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P4_START + P4_END)/2, y_pos, 'Tải nền\n(1 User)', transform=ax.get_xaxis_transform(), fontsize=10, color='#6a1b9a', fontweight='bold', ha='center', va='center', bbox=bbox_props)

# ==========================================
# 3. VẼ SIÊU DASHBOARD (2x2 GRID)
# ==========================================
fig = plt.figure(figsize=(24, 18)) 
fig.suptitle('BIỂU ĐỒ SO SÁNH HIỆU NĂNG KHI CÓ KEDA VÀ CHỨNG MINH KHẢ NĂNG SCALE UP - SCALE DOWN LINH HOẠT (KỊCH BẢN CPU)', fontsize=22, fontweight='bold', y=0.95)

outer_gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.25, wspace=0.15)

# --- PANEL 1. LOCUST RPS ---
inner_rps = outer_gs[0, 0].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_rps = fig.add_subplot(inner_rps[0])
add_phase_bg(ax_rps, show_labels=False)
ax_rps.plot(df_locust_no['Time_sec'], df_locust_no['Requests/s'], color=COLOR_NO, linewidth=2.5, label='Kịch bản NoKEDA')
ax_rps.plot(df_locust_with['Time_sec'], df_locust_with['Requests/s'], color=COLOR_WITH, linewidth=2.5, label='Kịch bản WithKEDA')
ax_rps.set_title('THÔNG LƯỢNG HỆ THỐNG (THROUGHPUT)', fontsize=16, fontweight='bold', pad=10)
ax_rps.set_ylabel('Requests / Giây (RPS)', fontsize=12, fontweight='bold')
# DỜI CHÚ THÍCH SANG GÓC TRÊN BÊN PHẢI (upper right)
ax_rps.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax_rps.grid(True, linestyle=':', alpha=0.6); ax_rps.set_ylim(bottom=0)

ax_user1 = fig.add_subplot(inner_rps[1], sharex=ax_rps)
add_phase_bg(ax_user1, show_labels=True)
ax_user1.plot(df_locust_with['Time_sec'], df_locust_with[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_user1.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_user1.set_xlabel('Thời gian thực thi (Giây)', fontsize=12, fontweight='bold')
ax_user1.legend(loc='upper right', fontsize=11); ax_user1.grid(True, linestyle=':', alpha=0.6)

# --- PANEL 2. LOCUST LATENCY ---
inner_lat = outer_gs[0, 1].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_lat = fig.add_subplot(inner_lat[0])
add_phase_bg(ax_lat, show_labels=False)
ax_lat.plot(df_locust_no['Time_sec'], df_locust_no[col_latency], color=COLOR_NO, linewidth=2.5, label='Kịch bản NoKEDA')
ax_lat.plot(df_locust_with['Time_sec'], df_locust_with[col_latency], color=COLOR_WITH, linewidth=2.5, label='Kịch bản WithKEDA')
ax_lat.axhline(1000, color='purple', linestyle=':', linewidth=2, label='SLA (1000ms)')
ax_lat.set_title('THỜI GIAN PHẢN HỒI (LATENCY)', fontsize=16, fontweight='bold', pad=10)
ax_lat.set_ylabel('Độ trễ (ms)', fontsize=12, fontweight='bold')
ax_lat.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax_lat.grid(True, linestyle=':', alpha=0.6); ax_lat.set_ylim(bottom=0)

ax_user2 = fig.add_subplot(inner_lat[1], sharex=ax_lat)
add_phase_bg(ax_user2, show_labels=True)
ax_user2.plot(df_locust_with['Time_sec'], df_locust_with[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_user2.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_user2.set_xlabel('Thời gian thực thi (Giây)', fontsize=12, fontweight='bold')
ax_user2.legend(loc='upper right', fontsize=11); ax_user2.grid(True, linestyle=':', alpha=0.6)

# --- TÍNH TOÁN TRỤC Y ĐỒNG NHẤT CHUNG CHO CẢ 2 MICROSERVICES ---
all_dfs = [fe_no, fe_with, pc_no, pc_with]

global_max_cpu = max([df['CPU'].max() if not df.empty else 0 for df in all_dfs])
# Bỏ hardcode 300. Tự động lấy đỉnh cao nhất cộng thêm 30% để tạo khoảng trống cho Legend!
GLOBAL_Y_LIMIT_CPU = 150 if global_max_cpu <= 150 else global_max_cpu * 1.3 

global_max_pods = max([df['Pods'].max() if not df.empty else 1 for df in all_dfs])
GLOBAL_Y_LIMIT_PODS = int(global_max_pods) + 2

# --- HÀM VẼ GRAPH CHO POD TỪ DATAFRAME TEXT ---
def draw_server_panel(gs_pos, df_no, df_with, title):
    inner_gf = outer_gs[gs_pos].subgridspec(2, 1, height_ratios=[1.8, 1], hspace=0.1)
    
    # 3.1 Biểu đồ CPU
    ax_c = fig.add_subplot(inner_gf[0])
    add_phase_bg(ax_c, show_labels=False) 
    
    if not df_no.empty:
        ax_c.plot(df_no['Time_sec'], df_no['CPU'], color=COLOR_NO, linewidth=2, linestyle='--', alpha=0.8, label='CPU (Kịch bản NoKEDA)')
    if not df_with.empty:
        ax_c.plot(df_with['Time_sec'], df_with['CPU'], color=COLOR_WITH, linewidth=2.5, label='CPU (Kịch bản WithKEDA)')
        ax_c.fill_between(df_with['Time_sec'], df_with['CPU'], color=COLOR_WITH, alpha=0.08)
        
    ax_c.axhline(70, color=COLOR_THRESH, linestyle=':', linewidth=2, label='Ngưỡng Scale (70%)')
    ax_c.set_title(f'{title}', fontsize=16, fontweight='bold', pad=10)
    ax_c.set_ylabel('CPU Usage (%)', fontsize=12, fontweight='bold')
    
    ax_c.set_ylim(0, GLOBAL_Y_LIMIT_CPU)
    
    # DỜI CHÚ THÍCH CPU SANG GÓC TRÊN BÊN PHẢI (upper right)
    ax_c.legend(loc='upper right', fontsize=11, ncol=2, framealpha=0.9)
    ax_c.grid(True, linestyle=':', alpha=0.6)
    
    # 3.2 Biểu đồ Pod
    ax_p = fig.add_subplot(inner_gf[1], sharex=ax_c)
    add_phase_bg(ax_p, show_labels=True) 
    if not df_no.empty:
        ax_p.plot(df_no['Time_sec'], df_no['Pods'], color=COLOR_POD_NO, linewidth=2.5, linestyle=':', alpha=0.8, label='Số Pod (NoKEDA)')
    if not df_with.empty:
        ax_p.plot(df_with['Time_sec'], df_with['Pods'], color=COLOR_POD_KEDA, linewidth=3.5, drawstyle='steps-post', label='Số Pod (WithKEDA)')
        ax_p.fill_between(df_with['Time_sec'], df_with['Pods'], step="post", color=COLOR_POD_KEDA, alpha=0.1)
    
    ax_p.set_ylabel('Số lượng Pods', fontsize=12, fontweight='bold')
    ax_p.set_xlabel('Thời gian thực thi (Giây)', fontsize=12, fontweight='bold')
    
    ax_p.set_yticks(range(0, GLOBAL_Y_LIMIT_PODS))
    ax_p.legend(loc='upper right', fontsize=11)
    ax_p.grid(True, linestyle=':', alpha=0.6)

# --- GỌI HÀM VẼ CHO CẢ 2 MICROSERVICES ---
draw_server_panel((1, 0), fe_no, fe_with, 'TÀI NGUYÊN CPU CỦA FRONTEND')
draw_server_panel((1, 1), pc_no, pc_with, 'TÀI NGUYÊN CPU CỦA PRODUCT CATALOG')

# XUẤT RA ĐỊNH DẠNG VECTOR
plt.savefig('Master_Dashboard_Final.png', dpi=300, bbox_inches='tight')
plt.savefig('Master_Dashboard_Final.svg', format='svg', bbox_inches='tight')
plt.close()

print("-> ĐÃ DỜI CHÚ THÍCH SANG GÓC PHẢI VÀ TỰ ĐỘNG CĂN LỀ Y! Hoàn hảo 100%!")