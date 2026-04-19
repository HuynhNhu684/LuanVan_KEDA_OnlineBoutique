import random
import math
import datetime
from locust import HttpUser, FastHttpUser, TaskSet, task, between, LoadTestShape
from faker import Faker

fake = Faker()

# Danh sách sản phẩm CHUẨN (trả về HTTP 200 / gRPC OK)
products = [
    '0PUK6V6EV0', '1YMWWN1N4O', '2ZYFJ3GM2N', '66VCHSJNUP',
    '6E92ZMYYFZ', '9SIQT8TOJO', 'L9ECAV7KIM', 'LS4PSXUNUM', 'OLJCESPC7Z'
]

# ==========================================
# CÁC HÀM MÔ PHỎNG HÀNH VI NGƯỜI DÙNG
# (Giải thích luồng đi của dữ liệu bên dưới hệ thống)
# ==========================================

def index(l):
    # TẢI TRANG CHỦ: Hành động này RẤT NẶNG cho Frontend.
    # Khi gọi "/", Frontend phải phân phát request đi gọi ProductCatalog (lấy list SP),
    # gọi AdService (lấy quảng cáo), gọi Currency (lấy tỷ giá), sau đó gom tất cả lại 
    # để Render (vẽ) ra cục HTML trả về cho khách. -> Tốn nhiều CPU và Network của Frontend.
    l.client.get("/")

def setCurrency(l):
    # ĐỔI TIỀN TỆ: Gửi mã tiền tệ (VD: USD, JPY).
    # Frontend nhận yêu cầu, gọi xuống CurrencyService để quy đổi, đồng thời 
    # lưu lựa chọn này vào Session (Cookie) của người dùng.
    currencies = ['EUR', 'USD', 'JPY', 'CAD', 'GBP', 'TRY']
    l.client.post("/setCurrency", {'currency_code': random.choice(currencies)})

def browseProduct(l):
    # XEM CHI TIẾT SẢN PHẨM: Hành động này bào mòn gRPC.
    # Frontend gọi thẳng xuống ProductCatalog qua giao thức gRPC để lấy thông tin 1 SP.
    # Dùng hàm này liên tục sẽ ép ProductCatalog phải Serialize (đóng gói) dữ liệu liên tục -> Tốn CPU nội bộ.
    l.client.get("/product/" + random.choice(products))

def viewCart(l):
    # XEM GIỎ HÀNG: Hành động I/O Bound (Nghẽn mạng/Disk).
    # Frontend gọi xuống CartService, CartService mở kết nối TCP chui xuống Redis để ĐỌC dữ liệu.
    l.client.get("/cart")

def addToCart(l):
    # THÊM VÀO GIỎ HÀNG: Hành động Stateful (Lưu trạng thái) nặng nhất.
    # Vừa phải truy xuất ProductCatalog để kiểm tra hàng, vừa phải bắt CartService 
    # GHI dữ liệu mới vào bộ nhớ của Redis -> Dùng để test Memory và I/O Queue rất tốt.
    product = random.choice(products)
    l.client.get("/product/" + product)
    l.client.post("/cart", {
        'product_id': product,
        'quantity': random.randint(1,10)})
    
def checkout(l):
    # THANH TOÁN: Cú "Final Boss" quét qua gần như toàn bộ hệ thống.
    # Luồng đi: Cart (lấy đồ) -> Shipping (tính phí ship) -> Currency (đổi tiền) 
    # -> Payment (trừ tiền) -> Email (gửi hóa đơn) -> Xóa giỏ hàng (Redis).
    # Nếu dùng hàm này liên tục, chỗ nào yếu nhất trong 11 Pod sẽ bị lộ diện ngay.
    addToCart(l)
    current_year = datetime.datetime.now().year + 1
    l.client.post("/cart/checkout", {
        'email': fake.email(),
        'street_address': fake.street_address(),
        'zip_code': fake.zipcode(),
        'city': fake.city(),
        'state': fake.state_abbr(),
        'country': fake.country(),
        'credit_card_number': fake.credit_card_number(card_type="visa"),
        'credit_card_expiration_month': random.randint(1, 12),
        'credit_card_expiration_year': random.randint(current_year, current_year + 70),
        'credit_card_cvv': f"{random.randint(100, 999)}",
    })

# ==========================================
# KỊCH BẢN TẢI TỔNG HỢP (MIX WORKLOAD)
# Dùng để test vận hành thực tế (Sẽ cần tính trọng số Toán học cho cái này)
# ==========================================
class UserBehavior(TaskSet):
    def on_start(self):
        index(self)

    # ĐIỀU CHỈNH TRỌNG SỐ (Tỷ lệ các hành động mô phỏng user thật)
    tasks = {
        index: 2,           # Khách vào trang chủ (Ít)
        setCurrency: 1,     # Đổi tiền tệ (Rất ít)
        browseProduct: 10,  # Lướt xem sản phẩm liên tục (Nhiều nhất)
        addToCart: 3,       # Thỉnh thoảng thêm vào giỏ
        viewCart: 2,        # Vào xem giỏ hàng
        checkout: 1         # Chốt đơn thanh toán (Ít nhất, vì làm khó hệ thống)
    }

# ==========================================
# CÁC KỊCH BẢN KIỂM THỬ CÔ LẬP (ISOLATED TESTS)
# Dùng để ép từng chỉ số vật lý vọt qua ngưỡng cấu hình của KEDA
# ==========================================

# 1. Kịch bản ép tải RPS (Tần suất yêu cầu)
# Phân bổ đều hỏa lực để tạo ra số lượng Request cực lớn trong 1 giây mà không bắt máy chủ làm quá nặng.
class RpsTestBehavior(TaskSet):
    def on_start(self):
        index(self)
    tasks = {
        index: 5, 
        browseProduct: 5
    }

# 2. Kịch bản ép tải CPU (Bão hòa tài nguyên tính toán)
# Bắt CPU của Product đóng gói gRPC liên tục và CPU Frontend render HTML liên tục.
class CpuTestBehavior(TaskSet):
    def on_start(self):
        index(self)
    tasks = {
        browseProduct: 10, 
        index: 2           
    }

# 3. Kịch bản tạo Tỷ lệ lỗi (Dựa trên Istio Timeout 3s)
# Ép CPU nghẽn cục bộ để thời gian xử lý vọt qua 3 giây, buộc Istio ném lỗi 50x.
class ErrorTestBehavior(TaskSet):
    def on_start(self):
        index(self)
    tasks = {
        browseProduct: 10,  
        index: 2            
    }

# 4. Kịch bản đo lường Bộ nhớ (Memory Saturation / Garbage Collection)
# Bắt hệ thống liên tục cấp phát RAM tạo Session mới. Ép Go Garbage Collector dọn dẹp không kịp.
class MemoryTestBehavior(TaskSet):
    def on_start(self):
        index(self)
    tasks = {
        addToCart: 10, 
        browseProduct: 1
    }

#Muốn chạy kịch bản nào thì mang tên Class ở trên thay vào trong dấu ngoặc vuông này
class WebsiteUser(FastHttpUser):
   tasks = [CpuTestBehavior] 
   wait_time = between(0.1, 0.2)

# Hàm dùng để test tìm ngưỡng của pod
# Tăng tốc StepLoad một chút để điểm gãy xuất hiện tầm phút thứ 3-4
# class StepLoadShape(LoadTestShape):
#      step_time = 20      # Cứ 20s tăng một lần (thay vì 30s)
#      step_users = 30     # Bơm hẳn 30 user mỗi nấc
#      spawn_rate = 10     
#      time_limit = 600

#      def tick(self):
#          run_time = self.get_run_time()
#          if run_time > self.time_limit:
#              return None
        
#          current_step = math.floor(run_time / self.step_time) + 1
#          return (current_step * self.step_users, self.spawn_rate)


# Kịch bản test độc lập chứng minh quá trình Scale-Up và Scale-Down của KEDA
class ReactiveScaleShape(LoadTestShape):
   def tick(self):
       run_time = self.get_run_time()
       
       # Giai đoạn 1: Khởi động (0 - 3 phút) 
       if run_time < 180: return (30, 5)
       
       # Giai đoạn 2: Đỉnh tải (3 - 10 phút) 
       elif run_time < 600: return (200, 10)
       
       # Giai đoạn 3: Giảm tải (10 - 15 phút) 
       elif run_time < 900: return (10, 20)
       
       # Giai đoạn 4: QUAN SÁT THU HỒI TÀI NGUYÊN (15 - 20 phút)
       # Bơm đúng 1 user để giữ Locust không bị tắt, ép Grafana ghi log đủ 20 phút
       elif run_time < 1200: return (1, 1) 
       
       else: return None

    

#class FlashSaleShopper(HttpUser):
#    wait_time = between(1, 2) # Người dùng thật thao tác khá nhanh khi có biến động
#
#    @task(10)
#    def browse(self):
#        self.client.get("/") 
#
#    @task(5)
#    def search(self):
#        self.client.get("/product/OLJCESPC7Z") 
#
#    @task(2)
#    def checkout(self):
#        self.client.post("/cart", json={"product_id": "OLJCESPC7Z", "quantity": 1})

#class WorldCupRealUnbiasedShape(LoadTestShape):
#    """
#    Kịch bản mô phỏng TRỰC DIỆN nhịp độ World Cup 1998.
#    Không kéo dài thời gian nghỉ, không ưu ái cấu hình.
#    Tổng thời gian: 20 phút (1200 giây) - Gọn, súc tích, tàn khốc.
#    """
#    trace_data = [
#        # 1. TRƯỚC TRẬN (0-3 ph): Khán giả vào sân, tải tăng đều.
#        {"time": 180, "users": 60, "spawn_rate": 2},
#        
#        # 2. HIỆP 1 BẮT ĐẦU (3-6 ph): Tải cao ổn định.
#        {"time": 360, "users": 150, "spawn_rate": 10}, 
#        
#        # 3. !!! GHI BÀN !!! (6-8 ph): Cú sốc cực đại, tăng vọt rồi giảm nhẹ ngay.
#        # Đây là đoạn test xem KEDA có "trở tay kịp" không.
#        {"time": 420, "users": 280, "spawn_rate": 100}, # Vọt lên 280 Users cực nhanh
#        {"time": 480, "users": 160, "spawn_rate": 50},  # Rớt xuống lại mức nền hiệp 1
#        
#        # 4. NGHỈ GIỮA HIỆP (8-12 ph): Tải GIẢM nhưng vẫn còn CAO (Fan thảo luận).
#        # Khoảng này chỉ có 4 phút, KEDA 600s sẽ KHÔNG kịp scale-down.
#        # Anh để đúng thực tế: Tải không rớt về 5-10 mà giữ ở mức 80.
#        {"time": 720, "users": 80, "spawn_rate": 20},
#        
#        # 5. HIỆP 2 QUYẾT ĐỊNH (12-17 ph): Tải đẩy lên mức cao nhất trận.
#        {"time": 1020, "users": 300, "spawn_rate": 30},
#        
    #     # 6. HẾT GIỜ (17-20 ph): Fan rời sân, tải rớt thẳng đứng.
    #     {"time": 1200, "users": 10, "spawn_rate": 100},

    #     # ========================================================
    #     # 7.SAU TRẬN ĐẤU (20-30 ph): GIAI ĐOẠN COOLDOWN (SCALE DOWN)
    #     # Bơm le lói 1 User để giữ cho Locust không bị tắt sớm,
    #     # ép KEDA hết 5 phút phải dọn dẹp RAM, thu hồi Pod từ 5 về 1.
    #     # ========================================================
    #     {"time": 1800, "users": 1, "spawn_rate": 1},
    # ]

    # def tick(self):
    #     run_time = self.get_run_time()
    #     for step in self.trace_data:
    #         if run_time < step["time"]:
    #             return (step["users"], step["spawn_rate"])
    #     return None
