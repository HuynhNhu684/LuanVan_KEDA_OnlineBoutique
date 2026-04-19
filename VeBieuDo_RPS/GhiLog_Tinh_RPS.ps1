$TARGETS = @(
    @{ name = "frontend"; threshold = 37 },
    @{ name = "productcatalogservice"; threshold = 83 }
)

Write-Host "PHUONG AN CUOI CUNG - CHAC CHAN RA SO..." -ForegroundColor Cyan

while($true) {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    foreach ($pod in $TARGETS) {
        $pod_name = $pod.name
        $pod_thresh = $pod.threshold
        
        # Dùng hàm rate kết hợp [30s] để ĐẢM BẢO luôn có dữ liệu trung bình mượt mà
        $query = 'sum(rate(istio_requests_total{destination_service=~"' + $pod_name + '.*"}[30s]))'
        
        $encodedQuery = [uri]::EscapeDataString($query)
        $url = "http://127.0.0.1:9090/api/v1/query?query=" + $encodedQuery
        
        try {
            $response = Invoke-RestMethod -Uri $url -Method Get
            $rps = 0
            
            if ($response.data.result.Count -gt 0) {
                $raw_value = $response.data.result[0].value[1]
                $rps = [math]::Round([double]$raw_value)
            }
            
            $log_line = "$time static-hpa-simulation Deployment/$pod_name prometheus-rps: $rps/$pod_thresh 1 1 1 1h"
            
            Write-Host $log_line
            $log_line | Out-File -FilePath "Log_Tinh_Standard_RPS.txt" -Append
            
        } catch {
            Write-Host "LOI: $_" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 5
}