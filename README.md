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
