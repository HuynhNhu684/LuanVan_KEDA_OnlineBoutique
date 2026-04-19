$TARGETS = @(
    @{ name = "frontend"; threshold = 128 }, 
    @{ name = "productcatalogservice"; threshold = 128 }
)

Write-Host "KHOI CHAY GIAM SAT BO NHO (MEMORY) - KICH BAN TINH..." -ForegroundColor Cyan

while($true) {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    foreach ($pod in $TARGETS) {
        $pod_name = $pod.name
        $pod_thresh = $pod.threshold
        
        # Dùng container_memory_working_set_bytes và chia cho (1024*1024) để đổi ra MiB
        $query = 'sum(container_memory_working_set_bytes{pod=~"' + $pod_name + '.*", container!=""}) / (1024 * 1024)'
        
        $encodedQuery = [uri]::EscapeDataString($query)
        $url = "http://127.0.0.1:9090/api/v1/query?query=" + $encodedQuery
        
        try {
            $response = Invoke-RestMethod -Uri $url -Method Get
            $mem_mib = 0
            
            if ($response.data.result.Count -gt 0) {
                $raw_value = $response.data.result[0].value[1]
                $mem_mib = [math]::Round([double]$raw_value, 1) # Làm tròn 1 chữ số thập phân
            }
            
            $log_line = "$time static-hpa-simulation Deployment/$pod_name prometheus-memory: ${mem_mib}Mi/${pod_thresh}Mi 1 1 1 1h"
            
            Write-Host $log_line
            $log_line | Out-File -FilePath "Log_Tinh_Standard_Memory.txt" -Append
            
        } catch {
            Write-Host "LOI: $_" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 5
}
