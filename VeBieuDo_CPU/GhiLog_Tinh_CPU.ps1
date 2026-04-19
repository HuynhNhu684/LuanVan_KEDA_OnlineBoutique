# Cấu hình chuẩn theo file YAML của em
$CPU_LIMIT = 100  # Cả 2 pod đều có limit là 100m
$TARGETS = @("frontend", "productcatalogservice") # Danh sách cần theo dõi

Write-Host "DANG KHOI DONG MAY GHI AM KEP CHO KICH BAN TINH..." -ForegroundColor Green

while($true) {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    # Quét lần lượt từng Pod trong danh sách
    foreach ($pod in $TARGETS) {
        $top = kubectl top pod -l app=$pod --no-headers | Select-String $pod
        
        if ($top) {
            # Tách lấy con số millicores (ví dụ '45m' -> 45)
            $val_m = [int]($top.ToString().Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)[1].Replace('m',''))
            
            # Tính phần trăm CPU dựa trên 100m
            $percent = [math]::Round(($val_m / $CPU_LIMIT) * 100)
            
            # Tạo dòng log giả lập HPA
            $log_line = "$time static-hpa-simulation Deployment/$pod cpu: $percent%/70% 1 1 1 1h"
            
            Write-Host $log_line
            $log_line | Out-File -FilePath "Log_Tinh_Standard.txt" -Append
        }
    }
    Start-Sleep -Seconds 5 # Nghỉ 5 giây rồi quét tiếp
}