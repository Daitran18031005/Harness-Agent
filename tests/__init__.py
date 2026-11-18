import os

# Test không nạp model Qwen (1,2 GB, GPU): backend chính sách cố định TF-IDF + router; test riêng của reranker tự đặt biến.
os.environ.setdefault("VECTOR_BACKEND", "tfidf")
# Test đếm lời gọi LLM giả viết trước HANDOFF_PREFETCH (cờ này thêm đúng 1 lời gọi kiểm duyệt mỗi lượt) và test bảng giá thường:
# giữ như cũ ở đây; HandoffPrefetchTest / FastPricingTest tự bật cờ.
os.environ.setdefault("HANDOFF_PREFETCH", "off")
os.environ.setdefault("LLM_SERVICE_TIER", "")
