$TARGETS = @(
    @{ name = "frontend"; threshold = "0.01" },
    @{ name = "productcatalogservice"; threshold = "0.01" }
)

Write-Host "KHOI DONG GHI LOG TY LE LOI (ERROR RATE)..." -ForegroundColor Cyan

while($true) {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    foreach ($pod in $TARGETS) {
        $pod_name = $pod.name
        $pod_thresh = $pod.threshold
        
        # Câu lệnh PromQL SIÊU CẤP: Chia (Tổng lỗi 5xx) cho (Tổng Request). 
        # Dùng "or vector(0)" để tránh lỗi tàng hình khi hệ thống đang bình thường không có lỗi nào.
        $query = '(sum(rate(istio_requests_total{destination_service=~"' + $pod_name + '.*", response_code=~"5.*"}[30s])) or vector(0)) / sum(rate(istio_requests_total{destination_service=~"' + $pod_name + '.*"}[30s]))'
        
        $encodedQuery = [uri]::EscapeDataString($query)
        $url = "http://127.0.0.1:9090/api/v1/query?query=" + $encodedQuery
        
        try {
            $response = Invoke-RestMethod -Uri $url -Method Get
            $error_rate = 0
            
            if ($response.data.result.Count -gt 0) {
                $raw_value = $response.data.result[0].value[1]
                
                # Kiểm tra tránh lỗi chia cho 0 của Prometheus (trả về NaN)
                if ($raw_value -ne "NaN") {
                    # Làm tròn 3 chữ số thập phân vì ngưỡng là 0.01
                    $error_rate = [math]::Round([double]$raw_value, 3)
                }
            }
            
            # Ghi log ra định dạng giống hệt KEDA: prometheus-error: 0.015/0.01
            $log_line = "$time static-hpa-simulation Deployment/$pod_name prometheus-error: $error_rate/$pod_thresh 1 1 1 1h"
            
            Write-Host $log_line
            $log_line | Out-File -FilePath "Log_Tinh_Standard_Error.txt" -Append
            
        } catch {
            Write-Host "LOI KET NOI PROMETHEUS: $_" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 5
}