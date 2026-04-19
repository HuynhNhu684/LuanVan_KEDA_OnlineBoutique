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

def load_memory_log(filename):
    """
    Hàm Trâu Bò: Xử lý file UTF-16 của PowerShell và mọi đơn vị m, k, Bytes, Mi của Kubernetes
    """
    data = []
    
    try:
        with open(filename, 'r', encoding='utf-16') as f:
            lines = f.readlines()
    except UnicodeError:
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"LỖI ĐỌC FILE: Không thể mở {filename}. Chi tiết: {e}")
            return pd.DataFrame(), pd.DataFrame()
            
    for line in lines:
        line = line.strip()
        if not line or 'NAME' in line or 'REFERENCE' in line:
            continue
        
        parts = line.split()
        if len(parts) < 8: 
            continue
        
        date_str = f"{parts[0]} {parts[1]}"
        
        service = "unknown"
        if "frontend" in line:
            service = "frontend"
        elif "productcatalogservice" in line:
            service = "productcatalogservice"
        
        if service == "unknown":
            continue

        match = re.search(r'([<a-zA-Z0-9\.]+)/(\d+)Mi', line)
        if not match:
            continue
            
        current_str = match.group(1).lower().replace(',', '.')
        if 'unknown' in current_str:
            continue
            
        try:
            if current_str.endswith('mi'):
                mem_val = float(current_str.replace('mi', ''))
            elif current_str.endswith('m'): 
                mem_val = float(current_str.replace('m', '')) / (1000.0 * 1024.0 * 1024.0)
            elif current_str.endswith('k') or current_str.endswith('ki'): 
                mem_val = float(current_str.replace('k', '').replace('i', '')) / 1024.0
            else: 
                mem_val = float(current_str) / (1024.0 * 1024.0)
        except ValueError:
            continue
            
        try:
            pod_val = int(parts[-2])
        except ValueError:
            continue
            
        data.append({'Datetime': date_str, 'Service': service, 'Memory': mem_val, 'Pods': pod_val})
            
    df = pd.DataFrame(data)
    if df.empty:
        print(f"CẢNH BÁO: Đọc {filename} thành công nhưng không có dữ liệu. K8s format thay đổi?")
        return pd.DataFrame(), pd.DataFrame()
        
    df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
    df = df.dropna(subset=['Datetime'])
    
    start_time = df['Datetime'].min()
    df['Time_sec'] = (df['Datetime'] - start_time).dt.total_seconds()
    
    df_fe = df[df['Service'] == 'frontend'].copy().sort_values('Time_sec')
    df_pc = df[df['Service'] == 'productcatalogservice'].copy().sort_values('Time_sec')
    
    return df_fe, df_pc

# ==========================================
# 2. NẠP DỮ LIỆU
# ==========================================
print("Đang nạp dữ liệu Tối thượng (Chấp mọi Log K8s, xuất cả PNG và SVG)...")

df_locust_no = load_and_clean_locust('No_KEDA_Memory_stats_history.csv')
df_locust_with = load_and_clean_locust('With_KEDA_Memory_stats_history.csv')

fe_no, pc_no = load_memory_log('Log_Tinh_Standard_Memory.txt')
fe_with, pc_with = load_memory_log('Log_KEDA_Memory.txt')

col_latency = 'Inst_Latency'
col_users = 'User Count'

MAX_TIME = min(df_locust_no['Time_sec'].max(), df_locust_with['Time_sec'].max())
if MAX_TIME < 1300: 
    MAX_TIME = max(df_locust_with['Time_sec'].max(), 1350) 

P1_START, P1_END = 0, 180           
P2_START, P2_END = 180, 600         
P3_START, P3_END = 600, 900         
P4_START, P4_END = 900, 1200        
P5_START, P5_END = 1200, MAX_TIME   

COLOR_NO, COLOR_WITH = '#e74c3c', '#1f77b4'
COLOR_POD_KEDA, COLOR_POD_NO = '#2ca02c', '#ff7f0e'

def add_phase_bg(ax, show_labels=False):
    ax.axvspan(P1_START, P1_END, color='#e0f7fa', alpha=0.5) 
    ax.axvspan(P2_START, P2_END, color='#fff9c4', alpha=0.5) 
    ax.axvspan(P3_START, P3_END, color='#c8e6c9', alpha=0.5) 
    ax.axvspan(P4_START, P4_END, color='#e1bee7', alpha=0.4) 
    ax.axvspan(P5_START, P5_END, color='#ffcdd2', alpha=0.6)

    if show_labels:
        bbox_props = dict(facecolor='white', alpha=0.8, edgecolor='none', boxstyle='round,pad=0.3')
        y_pos = 0.5 
        ax.text((P1_START + P1_END)/2, y_pos, 'Khởi động\n(30 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#00838f', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P2_START + P2_END)/2, y_pos, 'Đỉnh tải\n(200 Users)', transform=ax.get_xaxis_transform(), fontsize=11, color='#f57f17', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P3_START + P3_END)/2, y_pos, 'Hạ nhiệt\n(10 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#2e7d32', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P4_START + P4_END)/2, y_pos, 'Bẫy tĩnh\n(1 User)', transform=ax.get_xaxis_transform(), fontsize=10, color='#6a1b9a', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P5_START + P5_END)/2, y_pos, 'Can thiệp\n(Nâng 300Mi)', transform=ax.get_xaxis_transform(), fontsize=10, color='#b71c1c', fontweight='bold', ha='center', va='center', bbox=bbox_props)

# ==========================================
# 3. VẼ SIÊU DASHBOARD
# ==========================================
fig = plt.figure(figsize=(24, 18)) 
fig.suptitle('BIỂU ĐỒ SO SÁNH HIỆU NĂNG KHI CÓ KEDA VÀ CHỨNG MINH TÍNH SCALE UP - SCALE DOWN LINH HOẠT (KỊCH BẢN MEMORY)', fontsize=22, fontweight='bold', y=0.95)

outer_gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.25, wspace=0.15)

inner_rps = outer_gs[0, 0].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_rps = fig.add_subplot(inner_rps[0])
add_phase_bg(ax_rps, show_labels=False)
ax_rps.plot(df_locust_no['Time_sec'], df_locust_no['Requests/s'], color=COLOR_NO, linewidth=2.5, label='Kịch bản NoKEDA')
ax_rps.plot(df_locust_with['Time_sec'], df_locust_with['Requests/s'], color=COLOR_WITH, linewidth=2.5, label='Kịch bản WithKEDA')
ax_rps.set_title('THÔNG LƯỢNG HỆ THỐNG (THROUGHPUT)', fontsize=16, fontweight='bold', pad=10)
ax_rps.set_ylabel('Requests / Giây (RPS)', fontsize=12, fontweight='bold')
ax_rps.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax_rps.grid(True, linestyle=':', alpha=0.6); ax_rps.set_ylim(bottom=0)

ax_user1 = fig.add_subplot(inner_rps[1], sharex=ax_rps)
add_phase_bg(ax_user1, show_labels=True)
ax_user1.plot(df_locust_with['Time_sec'], df_locust_with[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_user1.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_user1.legend(loc='upper right', fontsize=11); ax_user1.grid(True, linestyle=':', alpha=0.6)

inner_lat = outer_gs[0, 1].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_lat = fig.add_subplot(inner_lat[0])
add_phase_bg(ax_lat, show_labels=False)
ax_lat.plot(df_locust_no['Time_sec'], df_locust_no[col_latency], color=COLOR_NO, linewidth=2.5, label='Kịch bản NoKEDA')
ax_lat.plot(df_locust_with['Time_sec'], df_locust_with[col_latency], color=COLOR_WITH, linewidth=2.5, label='Kịch bản WithKEDA')
ax_lat.set_title('THỜI GIAN PHẢN HỒI (LATENCY)', fontsize=16, fontweight='bold', pad=10)
ax_lat.set_ylabel('Độ trễ (ms)', fontsize=12, fontweight='bold')
ax_lat.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax_lat.grid(True, linestyle=':', alpha=0.6); ax_lat.set_ylim(bottom=0)

ax_user2 = fig.add_subplot(inner_lat[1], sharex=ax_lat)
add_phase_bg(ax_user2, show_labels=True)
ax_user2.plot(df_locust_with['Time_sec'], df_locust_with[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_user2.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_user2.legend(loc='upper right', fontsize=11); ax_user2.grid(True, linestyle=':', alpha=0.6)

global_max_pods = max([df['Pods'].max() if not df.empty else 1 for df in [fe_no, fe_with, pc_no, pc_with]])
GLOBAL_Y_LIMIT_PODS = int(global_max_pods) + 2

def draw_server_panel(gs_pos, df_no, df_with, title, threshold, intervention_time, intervention_val):
    inner_gf = outer_gs[gs_pos].subgridspec(2, 1, height_ratios=[1.8, 1], hspace=0.1)
    
    ax_c = fig.add_subplot(inner_gf[0])
    add_phase_bg(ax_c, show_labels=False) 
    
    # 1. Vẽ các đường Threshold MÀU ĐEN/TÍM siêu phân tách (zorder=2)
    ax_c.plot([0, intervention_time], [threshold, threshold], color='black', linestyle=':', linewidth=2.5, zorder=2, label=f'Ngưỡng ban đầu ({threshold}Mi)')
    ax_c.plot([intervention_time, MAX_TIME], [intervention_val, intervention_val], color='purple', linestyle='--', linewidth=2.5, zorder=2, label=f'Ngưỡng can thiệp ({intervention_val}Mi)')
    ax_c.plot([intervention_time, intervention_time], [threshold, intervention_val], color='purple', linestyle=':', linewidth=1.5, alpha=0.6, zorder=2)

    # 2. Vẽ các đường Dữ liệu RAM MÀU ĐỎ/XANH nổi bật (zorder=4)
    if not df_no.empty:
        ax_c.plot(df_no['Time_sec'], df_no['Memory'], color=COLOR_NO, linewidth=2.5, linestyle='--', alpha=0.9, zorder=4, label='MEMORY (NoKEDA)')
    if not df_with.empty:
        ax_c.plot(df_with['Time_sec'], df_with['Memory'], color=COLOR_WITH, linewidth=3, zorder=5, label='MEMORY (WithKEDA)')
        ax_c.fill_between(df_with['Time_sec'], df_with['Memory'], color=COLOR_WITH, alpha=0.08, zorder=1) # Bóng mờ chìm xuống đáy
        
    ax_c.set_ylim(0, intervention_val * 1.1) 
    ax_c.set_title(f'{title}', fontsize=16, fontweight='bold', pad=10)
    ax_c.set_ylabel('Memory / Pod (Mi)', fontsize=12, fontweight='bold')
    
    ax_c.legend(loc='upper left', fontsize=11, ncol=1, framealpha=0.9) 
    ax_c.grid(True, linestyle=':', alpha=0.6)
    
    ax_p = fig.add_subplot(inner_gf[1], sharex=ax_c)
    add_phase_bg(ax_p, show_labels=True) 
    if not df_no.empty:
        ax_p.plot(df_no['Time_sec'], df_no['Pods'], color=COLOR_POD_NO, linewidth=2.5, linestyle=':', alpha=0.8, label='Số Pod (NoKEDA)')
    if not df_with.empty:
        ax_p.plot(df_with['Time_sec'], df_with['Pods'], color=COLOR_POD_KEDA, linewidth=3.5, drawstyle='steps-post', label='Số (Pod WithKEDA)')
        ax_p.fill_between(df_with['Time_sec'], df_with['Pods'], step="post", color=COLOR_POD_KEDA, alpha=0.1)
    
    ax_p.set_ylabel('Số lượng Pods', fontsize=12, fontweight='bold')
    ax_p.set_xlabel('Thời gian thực thi (Giây)', fontsize=12, fontweight='bold')
    ax_p.set_yticks(range(0, GLOBAL_Y_LIMIT_PODS))
    ax_p.legend(loc='upper left', fontsize=11)
    ax_p.grid(True, linestyle=':', alpha=0.6)

# Vẽ 2 biểu đồ Server
draw_server_panel((1, 0), fe_no, fe_with, 'TÀI NGUYÊN BỘ NHỚ CỦA FRONTEND', threshold=80, intervention_time=1200, intervention_val=300)
draw_server_panel((1, 1), pc_no, pc_with, 'TÀI NGUYÊN BỘ NHỚ CỦA PRODUCT CATALOG', threshold=45, intervention_time=1200, intervention_val=300)

# ==========================================
# XUẤT RA 2 ĐỊNH DẠNG: PNG VÀ SVG
# ==========================================
plt.savefig('Master_Dashboard_Memory_Final.png', dpi=300, bbox_inches='tight')
plt.savefig('Master_Dashboard_Memory_Final.svg', format='svg', bbox_inches='tight')
plt.close()
 
print("-> VẼ BIỂU ĐỒ HOÀN TẤT! Đã xuất 2 file: Master_Dashboard_Memory_Final.png và Master_Dashboard_Memory_Final.svg thành công!")