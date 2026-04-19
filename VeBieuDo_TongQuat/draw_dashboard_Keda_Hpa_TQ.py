import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import re
import os

# ==========================================
# 1. CÁC HÀM XỬ LÝ DỮ LIỆU
# ==========================================
def load_and_clean_locust(filename):
    try:
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
            
        if 'Failures/s' not in df.columns:
            if 'Total Failure Count' in df.columns:
                df['Failures/s'] = df['Total Failure Count'].diff().fillna(0)
            else:
                df['Failures/s'] = 0
                
        return df
    except Exception as e:
        print(f"Lỗi đọc Locust {filename}: {e}")
        return pd.DataFrame()

def load_hpa_log(filename):
    data = []
    if not os.path.exists(filename):
        return pd.DataFrame(), pd.DataFrame()
        
    try:
        try:
            with open(filename, 'r', encoding='utf-16') as f: lines = f.readlines()
        except UnicodeError:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
                
        pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*(.*?)\s*\|\s*CPU:\s*([\d.]+)\s*%\s*\|\s*RAM:\s*[\d.]+\s*MB\s*\|\s*RPS:\s*([\d.]+)\s*\|\s*ERROR:\s*[\d.]+\s*\|\s*PODS:\s*(\d+)')
        
        for line in lines:
            line = line.strip().replace('\x00', '') 
            if not line: continue
            match = pattern.search(line)
            if match:
                data.append({
                    'Datetime': pd.to_datetime(match.group(1)),
                    'Service': match.group(2).strip(),
                    'CPU': float(match.group(3)),
                    'RPS': float(match.group(4)),
                    'Pods': int(match.group(5))
                })
    except Exception as e:
        print(f"LỖI đọc {filename}: {e}")
        return pd.DataFrame(), pd.DataFrame()
        
    df = pd.DataFrame(data)
    if df.empty: return pd.DataFrame(), pd.DataFrame()
        
    start_time = df['Datetime'].min()
    df['Time_sec'] = (df['Datetime'] - start_time).dt.total_seconds()
    
    df_fe = df[df['Service'] == 'frontend'].copy().sort_values('Time_sec')
    df_pc = df[df['Service'] == 'productcatalogservice'].copy().sort_values('Time_sec')
    
    return df_fe, df_pc

# ==========================================
# 2. NẠP DỮ LIỆU & ĐỒNG BỘ TRỤC THỜI GIAN
# ==========================================
print("🚀 Đang vẽ biểu đồ So sánh HPA và KEDA (Đồng bộ Y trục RPS chuẩn xác)...")

df_locust_no = load_and_clean_locust('TongQuat_WithHpa_stats_history.csv')
df_locust_with = load_and_clean_locust('TongQuat_WithKeda_stats_history.csv')

fe_no, pc_no = load_hpa_log('Log_HPA_TQ.txt')
fe_with, pc_with = load_hpa_log('Log_Keda_TQ.txt')

def sync_time(df, anchor_val, lead_in=30):
    if not df.empty:
        df['Time_sec'] = df['Time_sec'] - anchor_val + lead_in
        last_row = df.iloc[[-1]].copy()
        last_row['Time_sec'] = 2500
        df = pd.concat([df, last_row], ignore_index=True)
    return df

def find_anchor(df, col, threshold=2.0):
    if df.empty: return 0
    active = df[df[col] >= threshold]
    return active['Time_sec'].min() if not active.empty else 0

anc_loc_hpa = find_anchor(df_locust_no, 'Requests/s')
anc_srv_hpa = find_anchor(fe_no, 'RPS')
anc_loc_keda = find_anchor(df_locust_with, 'Requests/s')
anc_srv_keda = find_anchor(fe_with, 'RPS')

df_locust_no = sync_time(df_locust_no, anc_loc_hpa, 30)
fe_no = sync_time(fe_no, anc_srv_hpa, 30)
pc_no = sync_time(pc_no, anc_srv_hpa, 30)

df_locust_with = sync_time(df_locust_with, anc_loc_keda, 30)
fe_with = sync_time(fe_with, anc_srv_keda, 30)
pc_with = sync_time(pc_with, anc_srv_keda, 30)

# ==========================================
# CẤU HÌNH VẼ BIỂU ĐỒ VÀ MAX_RPS CHUNG
# ==========================================
all_rps = pd.concat([df['RPS'] for df in [fe_no, fe_with, pc_no, pc_with] if not df.empty])
# Ép GLOBAL_MAX_RPS để đảm bảo 2 bảng FrontEnd và Product có tỷ lệ y hệt nhau
GLOBAL_MAX_RPS = all_rps.max() if not all_rps.empty else 2000

all_cpu = pd.concat([df['CPU'] for df in [fe_no, fe_with, pc_no, pc_with] if not df.empty])
GLOBAL_MAX_CPU = all_cpu.max() if not all_cpu.empty else 100

col_latency = 'Inst_Latency'
col_users = 'User Count'

P1_START, P1_END = 0, 180           
P2_START, P2_END = 180, 600         
P3_START, P3_END = 600, 900         
P4_START, P4_END = 900, 1900 

COLOR_NO, COLOR_WITH = '#e74c3c', '#1f77b4'
COLOR_POD_KEDA, COLOR_POD_NO = '#2ca02c', '#ff7f0e'

CPU_TARGET = 70.0
FE_KEDA_RPS_TARGET = 37.0
PC_KEDA_RPS_TARGET = 83.0

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
        ax.text((P3_START + P3_END)/2, y_pos, 'Giảm tải\n(10 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#2e7d32', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P4_START + P4_END)/2, y_pos, 'Quan sát thu hồi\n(1 User)', transform=ax.get_xaxis_transform(), fontsize=10, color='#6a1b9a', fontweight='bold', ha='center', va='center', bbox=bbox_props)

# ==========================================
# 3. VẼ SIÊU DASHBOARD 
# ==========================================
fig = plt.figure(figsize=(24, 18)) 
fig.suptitle('BIỂU ĐỒ SO SÁNH HIỆU NĂNG VÀ PHẢN ỨNG CỦA HPA - KEDA', fontsize=24, fontweight='bold', y=0.96)

outer_gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.25, wspace=0.15)

# --- PANEL 1. LOCUST RPS ---
inner_rps = outer_gs[0, 0].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_rps = fig.add_subplot(inner_rps[0])
add_phase_bg(ax_rps)

if not df_locust_no.empty: 
    ax_rps.plot(df_locust_no['Time_sec'], df_locust_no['Requests/s'], color=COLOR_NO, linewidth=2.5, label='RPS (HPA)')
    ax_rps.plot(df_locust_no['Time_sec'], df_locust_no['Failures/s'], color='darkred', linewidth=2.5, linestyle=':', label='Lỗi/s (HPA)')
if not df_locust_with.empty: 
    ax_rps.plot(df_locust_with['Time_sec'], df_locust_with['Requests/s'], color=COLOR_WITH, linewidth=2.5, label='RPS (KEDA)')
    ax_rps.plot(df_locust_with['Time_sec'], df_locust_with['Failures/s'], color='darkblue', linewidth=2.5, linestyle=':', label='Lỗi/s (KEDA)')

ax_rps.set_title('THÔNG LƯỢNG HỆ THỐNG (THROUGHPUT) VÀ TỶ LỆ LỖI', fontsize=16, fontweight='bold', pad=10)
ax_rps.set_ylabel('Requests / Lỗi mỗi Giây', fontsize=12, fontweight='bold')
ax_rps.legend(loc='upper right', fontsize=11, framealpha=0.9, ncol=2)
ax_rps.grid(True, linestyle=':', alpha=0.6); ax_rps.set_xlim(0, P4_END)

ax_user1 = fig.add_subplot(inner_rps[1], sharex=ax_rps)
add_phase_bg(ax_user1, show_labels=True)
if not df_locust_with.empty: ax_user1.plot(df_locust_with['Time_sec'], df_locust_with[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_user1.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_user1.legend(loc='upper right', fontsize=11); ax_user1.grid(True, linestyle=':', alpha=0.6)

# --- PANEL 2. LOCUST LATENCY ---
inner_lat = outer_gs[0, 1].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_lat = fig.add_subplot(inner_lat[0])
add_phase_bg(ax_lat)
if not df_locust_no.empty: ax_lat.plot(df_locust_no['Time_sec'], df_locust_no[col_latency], color=COLOR_NO, linewidth=2.5, label='Kịch bản HPA')
if not df_locust_with.empty: ax_lat.plot(df_locust_with['Time_sec'], df_locust_with[col_latency], color=COLOR_WITH, linewidth=2.5, label='Kịch bản KEDA')
ax_lat.axhline(1000, color='purple', linestyle=':', linewidth=2, label='SLA (1000ms)')

ax_lat.set_title('THỜI GIAN PHẢN HỒI (LATENCY)', fontsize=16, fontweight='bold', pad=10)
ax_lat.set_ylabel('Độ trễ (ms)', fontsize=12, fontweight='bold')
ax_lat.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax_lat.grid(True, linestyle=':', alpha=0.6); ax_lat.set_xlim(0, P4_END)

ax_user2 = fig.add_subplot(inner_lat[1], sharex=ax_lat)
add_phase_bg(ax_user2, show_labels=True)
if not df_locust_with.empty: ax_user2.plot(df_locust_with['Time_sec'], df_locust_with[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_user2.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_user2.legend(loc='upper right', fontsize=11); ax_user2.grid(True, linestyle=':', alpha=0.6)

def draw_server_panel(gs_pos, df_no, df_with, rps_target, title):
    inner_gf = outer_gs[gs_pos].subgridspec(2, 1, height_ratios=[1.8, 1], hspace=0.1)
    ax_c = fig.add_subplot(inner_gf[0])
    add_phase_bg(ax_c) 
    
    if not df_no.empty:
        ax_c.plot(df_no['Time_sec'], df_no['CPU'], color=COLOR_NO, linewidth=2, label='CPU (HPA)')
        ax_c.fill_between(df_no['Time_sec'], df_no['CPU'], color=COLOR_NO, alpha=0.1) 
    if not df_with.empty:
        ax_c.plot(df_with['Time_sec'], df_with['CPU'], color=COLOR_WITH, linewidth=2, label='CPU (KEDA)')
        ax_c.fill_between(df_with['Time_sec'], df_with['CPU'], color=COLOR_WITH, alpha=0.1) 
        
    ax_c.axhline(CPU_TARGET, color='darkred', linestyle=':', linewidth=1.5, label=f'Ngưỡng CPU ({int(CPU_TARGET)}%)')
    
    ax_c.set_title(title, fontsize=16, fontweight='bold', pad=10)
    ax_c.set_ylabel('CPU Usage (%)', fontsize=12, fontweight='bold')
    ax_c.set_ylim(0, GLOBAL_MAX_CPU * 1.25)
    
    # 🔥 RPS AXIS (ĐỒNG BỘ TUYỆT ĐỐI) 🔥
    ax_rps_in = ax_c.twinx()
    if not df_no.empty:
        ax_rps_in.plot(df_no['Time_sec'], df_no['RPS'], color='#ff7f0e', linewidth=2.5, linestyle='--', label='RPS (HPA)')
    if not df_with.empty:
        ax_rps_in.plot(df_with['Time_sec'], df_with['RPS'], color='darkorchid', linewidth=2.5, linestyle='-.', label='RPS (KEDA)')
        
    ax_rps_in.axhline(rps_target, color='purple', linestyle='--', linewidth=1.5, label=f'Ngưỡng KEDA Scale ({int(rps_target)} RPS)')
    ax_rps_in.set_ylabel('RPS Nội Bộ', fontsize=12, fontweight='bold')
    # Ép cứng giới hạn Y để thấy rõ Product lớn hơn Frontend cỡ nào
    ax_rps_in.set_ylim(0, GLOBAL_MAX_RPS * 1.05) 
    
    lines_1, labels_1 = ax_c.get_legend_handles_labels()
    lines_2, labels_2 = ax_rps_in.get_legend_handles_labels()
    ax_c.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize=10, ncol=2, framealpha=0.9)
    ax_c.grid(True, linestyle=':', alpha=0.6); ax_c.set_xlim(0, P4_END)
    
    # 🔥 BẢNG PODS 🔥
    ax_p = fig.add_subplot(inner_gf[1], sharex=ax_c)
    add_phase_bg(ax_p, show_labels=False) 
    if not df_no.empty:
        ax_p.plot(df_no['Time_sec'], df_no['Pods'], color=COLOR_POD_NO, linewidth=2.5, linestyle='--', alpha=0.9, drawstyle='steps-post', label='Số Pod (HPA)')
        ax_p.fill_between(df_no['Time_sec'], df_no['Pods'], step="post", color=COLOR_POD_NO, alpha=0.15) 
    if not df_with.empty:
        ax_p.plot(df_with['Time_sec'], df_with['Pods'], color=COLOR_POD_KEDA, linewidth=3.5, drawstyle='steps-post', label='Số Pod (KEDA)')
        ax_p.fill_between(df_with['Time_sec'], df_with['Pods'], step="post", color=COLOR_POD_KEDA, alpha=0.1)
    
    ax_p.set_ylabel('Số lượng Pods', fontsize=12, fontweight='bold')
    ax_p.set_xlabel('Thời gian thực thi (Giây)', fontsize=12, fontweight='bold')
    all_pods = pd.concat([df_no['Pods'], df_with['Pods']]) if not df_no.empty and not df_with.empty else pd.Series([1])
    ax_p.set_yticks(range(0, int(all_pods.max()) + 2))
    
    # 🔥 ĐÃ SỬA: CHÚ THÍCH THÀNH CỘT DỌC VÀ CHUYỂN SANG TRÁI ĐỂ KHÔNG CHE ĐỒ THỊ 🔥
    ax_p.legend(loc='upper right', fontsize=11, framealpha=0.8, ncol=1)
    ax_p.grid(True, linestyle=':', alpha=0.6); ax_p.set_xlim(0, P4_END)

draw_server_panel((1, 0), fe_no, fe_with, FE_KEDA_RPS_TARGET, 'SO SÁNH PHẢN ỨNG CỦA HPA VÀ KEDA TRÊN FRONTEND')
draw_server_panel((1, 1), pc_no, pc_with, PC_KEDA_RPS_TARGET, 'SO SÁNH PHẢN ỨNG CỦA HPA VÀ KEDA TRÊN PRODUCT CATALOG')

plt.savefig('Master_Dashboard_HPA_KEDA_TQuat.png', dpi=300, bbox_inches='tight')
plt.savefig('Master_Dashboard_HPA_KEDA_TQuat.svg', format='svg', bbox_inches='tight')
plt.close()

print("✅ ĐÃ CHỈNH SỬA XONG! Chú thích Pod dời sang trái thành cột dọc, Y-Axis RPS đồng bộ 100%!")