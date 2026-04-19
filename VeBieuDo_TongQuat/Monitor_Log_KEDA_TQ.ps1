$CPU_LIMIT = 100 
$TARGETS = @("frontend", "productcatalogservice")

# Đảm bảo em đã mở port-forward Prometheus ra cổng 9090 trước khi chạy nhé
$PROMETHEUS_URL = "http://localhost:9090/api/v1/query?query="

Write-Host "🚀 DANG KHOI DONG MAY GHI LOG (DONG BO 100% KEDA YAML)..." -ForegroundColor Green

while($true) {
    # Lấy thời gian 1 lần cho cả 2 service để lúc lên biểu đồ X-axis bằng nhau tuyệt đối
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    foreach ($pod in $TARGETS) {
        # ==========================================
        # 1. NATIVE METRICS (CPU & RAM) - Y như KEDA Trigger 1 & 2
        # ==========================================
        $cpu_pct = 0
        $ram_mb = 0
        try {
            # Lấy dòng đầu tiên để tránh lỗi khi có nhiều Pods
            $top = kubectl top pod -l app=$pod --no-headers | Select-Object -First 1
            # Dùng Regex để gắp số an toàn, bỏ qua nếu K8s lag trả về <unknown>
            if ($top -match "(\d+)m\s+(\d+)Mi") {
                $cpu_m = [int]$matches[1]
                $cpu_pct = [math]::Round(($cpu_m / $CPU_LIMIT) * 100, 2)
                $ram_mb = [int]$matches[2]
            }
        } catch {}

        # ==========================================
        # 2. EXTERNAL METRICS (RPS) - Y như KEDA Trigger 3
        # ==========================================
        $q_rps = "sum(rate(istio_requests_total{destination_service=~`"$pod.*`"}[30s])) or vector(0)"
        $rps = 0
        try {
            $res_rps = Invoke-RestMethod -Uri ($PROMETHEUS_URL + [System.Uri]::EscapeDataString($q_rps)) -ErrorAction Ignore
            if ($res_rps.data.result.Count -gt 0) { 
                $rps = [math]::Round([decimal]$res_rps.data.result[0].value[1], 3) 
            }
        } catch {}

        # ==========================================
        # 3. EXTERNAL METRICS (ERROR) - Y như KEDA Trigger 4
        # ==========================================
        $q_err = "(sum(rate(istio_requests_total{destination_service=~`"$pod.*`", response_code=~`"5.*`"}[30s])) / sum(rate(istio_requests_total{destination_service=~`"$pod.*`"}[2m]))) or vector(0)"
        $err = 0
        try {
            $res_err = Invoke-RestMethod -Uri ($PROMETHEUS_URL + [System.Uri]::EscapeDataString($q_err)) -ErrorAction Ignore
            if ($res_err.data.result.Count -gt 0 -and $res_err.data.result[0].value[1] -ne "NaN") { 
                $err = [math]::Round([decimal]$res_err.data.result[0].value[1], 4) 
            }
        } catch {}

        # ==========================================
        # 4. SỐ POD THỰC TẾ
        # ==========================================
        $so_pod = 0
        try {
            $so_pod_str = kubectl get deployment $pod -o=jsonpath='{.status.readyReplicas}'
            if (-not [string]::IsNullOrWhiteSpace($so_pod_str)) { $so_pod = [int]$so_pod_str }
        } catch {}

        # ==========================================
        # 5. GHI LOG TỔNG HỢP VÀO 1 DÒNG DUY NHẤT
        # ==========================================
        $log_line = "$time | $pod | CPU: $cpu_pct % | RAM: $ram_mb MB | RPS: $rps | ERROR: $err | PODS: $so_pod"
        
        Write-Host $log_line -ForegroundColor Cyan
        
        # Đổi tên file ở đây (Log_HPA.txt hoặc Log_Keda.txt)
        $log_line | Out-File -FilePath "Log_KEDA_TQ.txt" -Append -Encoding UTF8
    }
    
    # Nghỉ 5 giây - Quét mịn màng để không trượt mốc scale nào
    Start-Sleep -Seconds 5
}