# LUẬN VĂN TỐT NGHIỆP: TỰ ĐỘNG CO GIÃN TÀI NGUYÊN CHO KIẾN TRÚC MICROSERVICES DỰA TRÊN PHẢN ỨNG ĐA CHIỀU

**Sinh viên thực hiện:** Lê Huỳnh Như  
**Chuyên ngành:** Mạng máy tính và Truyền thông dữ liệu - Đại học Cần Thơ  
**Giảng viên hướng dẫn:** [TS. Nguyễn Hữu Vân Long]

---

## 📝 1. Giới thiệu đề tài
Đề tài tập trung nghiên cứu và triển khai giải pháp **Reactive Autoscaling đa chiều** sử dụng công cụ **KEDA** trên nền tảng Kubernetes. Khác với cơ chế truyền thống chỉ dựa trên một chiều tài nguyên (CPU/RAM), nghiên cứu này thực hiện co giãn dựa trên sự kết hợp đa chỉ số (multi-metrics) bao gồm: 
- **Chỉ số sự kiện (Event-driven):** Số lượng yêu cầu trên giây (RPS).
- **Chỉ số tài nguyên (Resource-based):** Mức độ chiếm dụng CPU và RAM.

Cách tiếp cận đa chiều này giúp hệ thống Microservices phản ứng linh hoạt, chính xác hơn trước các biến động lưu lượng, đồng thời tối ưu hóa việc sử dụng tài nguyên và đảm bảo chất lượng dịch vụ (SLA).

## 🏗 2. Kiến trúc thực nghiệm
Hệ thống được triển khai dựa trên mô hình **Online Boutique** với các thành phần:
- **Hạ tầng:** Kubernetes (Kind), Istio Service Mesh.
- **Autoscaling:** KEDA (Kubernetes Event-driven Autoscaling) điều phối HPA.
- **Observability:** Prometheus thu thập dữ liệu, Metrics Server giám sát tài nguyên.
- **Kiểm thử:** Locust (Load Testing) dùng để mô phỏng tải thực tế và xác định ngưỡng tối ưu (Knee of the curve).

## 📁 3. Các thành phần đóng góp chính (Contributions)
Mã nguồn luận văn bao gồm các thành phần quan trọng do sinh viên phát triển và cấu hình để hiện thực hóa cơ chế co giãn đa chiều:

### 🔹 Cấu hình Kubernetes & Autoscaling (thư mục /release):
- **keda-product.yaml & keda-frontend.yaml**: Định nghĩa các `ScaledObject` để thực hiện co giãn đa chiều (kết hợp RPS và CPU) cho dịch vụ Product và Frontend.
- **hpa-traditional.yaml**: Cấu hình bộ tự động co giãn HPA truyền thống để phục vụ việc so sánh, đối chứng hiệu năng.
- **istio-manifests.yaml**: Cấu hình Istio Service Mesh (Gateway, VirtualService) nhằm quản lý lưu lượng và cung cấp các chỉ số telemetry (RPS) chính xác cho Prometheus.
- **frontend-ingress.yaml**: Cấu hình Ingress để điều hướng lưu lượng từ bên ngoài vào hệ thống.
- **optimal-dr.yaml**: Các tham số cấu hình ngưỡng tối ưu phục vụ cho việc thực nghiệm xác định điểm uốn (Knee of the curve).

### 🔹 Bộ công cụ phân tích dữ liệu:
- **/VeBieuDo_.../**: Tập hợp các script (Python, PowerShell) tự động hóa quy trình thu thập dữ liệu từ Kubernetes API và Prometheus để vẽ biểu đồ phân tích.
- **/src/loadgenerator/locustfile.py**: Kịch bản kiểm thử tải mô phỏng các mẫu traffic thực tế để đánh giá độ nhạy của bộ co giãn đa chiều.

## 🛠 4. Yêu cầu hệ thống (Prerequisites)
Để triển khai hệ thống này, máy tính cần cài đặt sẵn các công cụ sau:
- **Docker Desktop** (hoặc Docker Engine trên Linux).
- **Kind** (Kubernetes in Docker) để khởi tạo cụm K8s local.
- **Kubectl**: Công cụ dòng lệnh quản lý Kubernetes.
- **Helm**: Bộ quản lý gói để cài đặt KEDA và Istio.
- **Python 3.x**: Để chạy script vẽ biểu đồ và công cụ Locust.

## 🚀 5. Quy trình thực hiện (Usage)

### Bước 1: Khởi tạo cụm K8s với Kind
```bash
kind create cluster --config ./release/kind-config.yaml
Bước 2: Triển khai ứng dụng Online Boutique
Triển khai hệ thống microservices mẫu để làm môi trường thực nghiệm.

Bash
# Clone mã nguồn dự án
git clone [https://github.com/GoogleCloudPlatform/microservices-demo.git](https://github.com/GoogleCloudPlatform/microservices-demo.git) online_boutique
cd online_boutique

# Deploy ứng dụng lên cluster
kubectl apply -f release/kubernetes-manifests.yaml

# Tắt bot tạo tải ngầm mặc định để chuẩn bị cho kịch bản Load Test riêng
kubectl scale deployment loadgenerator --replicas=0
Sơ đồ kiến trúc tổng thể:
(Hình ảnh minh họa 11 dịch vụ giao tiếp qua gRPC)

Bước 3: Thiết lập hệ thống giám sát (Monitoring)
Cài đặt Prometheus và Grafana để thu thập, quan sát các chỉ số RPS, CPU và RAM.

Bash
# Tạo namespace cho monitoring
kubectl create namespace monitoring

# Cài đặt Prometheus
helm repo add prometheus-community [https://prometheus-community.github.io/helm-charts](https://prometheus-community.github.io/helm-charts)
helm repo update
helm install prometheus prometheus-community/prometheus --namespace monitoring

# Cài đặt Grafana
helm repo add grafana [https://grafana.github.io/helm-charts](https://grafana.github.io/helm-charts)
helm install grafana grafana/grafana --namespace monitoring

# Lấy mật khẩu đăng nhập Grafana (Giải mã chuỗi Base64)
kubectl get secret --namespace monitoring grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
Ghi chú: Kết nối Prometheus Data Source trong Grafana tại địa chỉ nội bộ: http://prometheus-server.monitoring.svc.cluster.local

Bước 4: Cài đặt bộ co giãn KEDA và Metrics Server
Thiết lập công cụ lấy metric tài nguyên và Operator thực thi co giãn đa chiều.

Bash
# Cài đặt KEDA
helm repo add kedacore [https://kedacore.github.io/charts](https://kedacore.github.io/charts)
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace

# Cài đặt Metrics Server (Bản chuẩn)
kubectl apply -f [https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml](https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml)

# Vá lỗi xác thực TLS cho Metrics Server trên môi trường Local (Kind)
kubectl patch deployment metrics-server -n kube-system --type=json -p="[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/args/-\", \"value\": \"--kubelet-insecure-tls\"}]"
Bước 5: Chạy kiểm thử và Thu thập kết quả
Tiến hành đẩy tải vào hệ thống và kích hoạt các script lưu trữ log.

Bash
# 1. Khởi chạy Locust theo kịch bản xác định điểm uốn
locust -f ./src/loadgenerator/locustfile.py

# 2. Thu thập log tự động (Sử dụng PowerShell)
./VeBieuDo_TongQuat/Monitor_Log_KEDA_TQ.ps1

# 3. Vẽ biểu đồ phân tích đa chiều
python ./VeBieuDo_TongQuat/draw_dashboard_Keda_NoKeda_TQ.py
📉 6. Kết quả thực nghiệm (Results)
Hệ thống co giãn đa chiều (sử dụng KEDA kết hợp RPS + CPU) đã chứng minh được:

Tốc độ phản ứng: Scale-up nhanh chóng ngay khi lưu lượng (RPS) có dấu hiệu tăng đột biến, tránh được độ trễ khởi động của HPA truyền thống.

Đảm bảo SLA: Duy trì thời gian phản hồi (Response Time) ở mức ổn định dưới ngưỡng cho phép trong suốt quá trình chịu tải.

Tối ưu tài nguyên: Tự động thu hồi (Scale-down) số lượng Pod về mức tối thiểu khi không có request, giúp tiết kiệm tối đa chi phí hạ tầng.

(Ghi chú: Xem chi tiết các biểu đồ so sánh trong thư mục /VeBieuDo_TongQuat)

🤝 Thông tin liên hệ
Sinh viên: Lê Huỳnh Như

Đơn vị: Khoa Công nghệ Thông tin & Truyền thông - Đại học Cần Thơ (CTU).

Github Profile: HuynhNhu684
